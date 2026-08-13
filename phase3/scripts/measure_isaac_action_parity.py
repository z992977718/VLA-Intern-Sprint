#!/usr/bin/env python3
"""Execute exactly one canonical action through Action Adapter -> Safety -> PINK -> Franka."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
from isaacsim import SimulationApp

from action_adapter_step4 import SafetyConfig, adapt_libero_action, matrix_to_quaternion_wxyz
from isaac_step6_scene_gate import build_scene, prim_world_pose
from phase3_step6_common import EEF_OFFSET_IN_HAND_M, JOINT_NAMES, PHYSICS_DT, quaternion_wxyz_to_matrix

CASES = {
    "+X": [0.10, 0, 0, 0, 0, 0, 0], "-X": [-0.10, 0, 0, 0, 0, 0, 0],
    "+Y": [0, 0.10, 0, 0, 0, 0, 0], "-Y": [0, -0.10, 0, 0, 0, 0, 0],
    "+Z": [0, 0, 0.10, 0, 0, 0, 0], "-Z": [0, 0, -0.10, 0, 0, 0, 0],
    "+Rx": [0, 0, 0, 0.05, 0, 0, 0], "-Rx": [0, 0, 0, -0.05, 0, 0, 0],
    "+Ry": [0, 0, 0, 0, 0.05, 0, 0], "-Ry": [0, 0, 0, 0, -0.05, 0, 0],
    "+Rz": [0, 0, 0, 0, 0, 0.05, 0], "-Rz": [0, 0, 0, 0, 0, -0.05, 0],
    "open": [0, 0, 0, 0, 0, 0, -1], "close": [0, 0, 0, 0, 0, 0, 1],
}


def axis_angle(matrix: np.ndarray) -> list[float]:
    angle = float(np.arccos(np.clip((np.trace(matrix) - 1.0) / 2.0, -1.0, 1.0)))
    if angle < 1e-9: return [0.0, 0.0, 0.0]
    axis = np.array([matrix[2, 1]-matrix[1, 2], matrix[0, 2]-matrix[2, 0], matrix[1, 0]-matrix[0, 1]])
    return (axis / (2 * np.sin(angle)) * angle).tolist()


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--case", choices=CASES); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    output = args.output.resolve()
    if output.exists(): raise FileExistsError(f"refusing to overwrite {output}")
    app = SimulationApp({"headless": True, "renderer": "RaytracedLighting"})
    try:
        import warp as wp
        import isaacsim.robot_motion.experimental.motion_generation as mg
        from isaacsim.core.utils.extensions import enable_extension
        enable_extension("isaacsim.robot_motion.pink")
        for _ in range(10):
            app.update()
        from isaacsim.robot_motion.pink import PinkIKController, load_pink_supported_robot
        scene = build_scene(app, 0, dynamic_objects=False); world, stage, robot = scene["world"], scene["stage"], scene["robot"]
        hand = next(p for p in stage.Traverse() if p.GetName() == "panda_hand"); hand_path = str(hand.GetPath())
        def eef():
            hp, hq = prim_world_pose(stage, scene["Usd"], scene["UsdGeom"], hand_path); hr = quaternion_wxyz_to_matrix(hq)
            return hp + hr @ EEF_OFFSET_IN_HAND_M, hr
        before_pos, before_rot = eef()
        safety = SafetyConfig(workspace_min_xyz_m=(-0.35, -0.55, 0.40), workspace_max_xyz_m=(0.30, 0.70, 1.05))
        bounded = adapt_libero_action(np.asarray(CASES[args.case]), before_pos, before_rot, safety)
        base_pos = np.asarray(scene["reference"]["robot_base_position_xyz_m"]); base_rot = quaternion_wxyz_to_matrix(np.asarray(scene["reference"]["robot_base_quaternion_wxyz"]))
        target_rot = np.asarray(bounded["target_orientation_matrix"]); target_pos = np.asarray(bounded["target_position_xyz_m"])
        target_hand_pos = target_pos - target_rot @ EEF_OFFSET_IN_HAND_M
        pink = PinkIKController(pink_robot=load_pink_supported_robot("franka"), robot_joint_space=list(JOINT_NAMES), robot_site_space=["panda_hand"], tool_frame="panda_hand", position_cost=5.0, orientation_cost=0.05, posture_cost=5e-3, solver="osqp", dt=PHYSICS_DT)
        def state(): return mg.RobotState(joints=mg.JointState.from_name(robot_joint_space=list(JOINT_NAMES), positions=(list(JOINT_NAMES), robot.get_dof_positions()), velocities=(list(JOINT_NAMES), robot.get_dof_velocities())))
        setpoint = mg.RobotState(sites=mg.SpatialState.from_name(spatial_space=["panda_hand"], positions=(["panda_hand"], wp.from_numpy(np.asarray([base_rot.T @ (target_hand_pos - base_pos)], np.float32), dtype=wp.float32, device="cpu")), orientations=(["panda_hand"], wp.from_numpy(np.asarray([matrix_to_quaternion_wxyz(base_rot.T @ target_rot)], np.float32), dtype=wp.float32, device="cpu"))))
        if not pink.reset(state(), setpoint, 0): raise RuntimeError("PINK reset failed")
        lower_raw, upper_raw = robot.get_dof_limits(); lower, upper = lower_raw.numpy()[0], upper_raw.numpy()[0]
        for index in range(3):
            desired = pink.forward(state(), setpoint, index * PHYSICS_DT)
            if desired is None or desired.joints.positions is None: raise RuntimeError("PINK forward failed")
            target = desired.joints.positions.numpy().astype(np.float64); indices = desired.joints.position_indices.numpy().astype(int)
            current = robot.get_dof_positions().numpy()[0]
            if not np.isfinite(target).all(): raise RuntimeError("non-finite PINK joint target")
            if np.max(np.abs(target - current[indices])) > 0.05: raise RuntimeError("joint step safety limit")
            if np.any(target < lower[indices]) or np.any(target > upper[indices]): raise RuntimeError("joint limit safety rejection")
            robot.set_dof_position_targets(target.astype(np.float32), dof_indices=indices)
            if index == 0:
                finger = 0.0 if bounded["gripper_command"] > 0.1 else (0.04 if bounded["gripper_command"] < -0.1 else float(np.mean(robot.get_dof_positions().numpy()[0][7:])))
                robot.set_dof_position_targets(np.array([finger, finger], np.float32), dof_indices=np.array([7, 8]))
            world.step(render=False)
        after_pos, after_rot = eef(); q = robot.get_dof_positions().numpy()[0]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"case": args.case, "raw_normalized_action": CASES[args.case], "independent_process_and_scene_reset": True, "physics_steps": 3, "control_duration_sec": 0.05, "bounded": bounded, "eef_before_xyz_m": before_pos.tolist(), "eef_after_xyz_m": after_pos.tolist(), "actual_delta_xyz_m": (after_pos-before_pos).tolist(), "actual_displacement_m": float(np.linalg.norm(after_pos-before_pos)), "rotation_before_matrix": before_rot.tolist(), "rotation_after_matrix": after_rot.tolist(), "relative_rotation_axis_angle_rad": axis_angle(after_rot @ before_rot.T), "gripper_after_qpos": q[7:].tolist(), "gripper_semantic": "OPEN" if CASES[args.case][6] < 0 else ("CLOSED" if CASES[args.case][6] > 0 else "HOLD"), "safety_intervention": bool(bounded["clipping_applied"]), "safety_status": "PASS", "joint_safety": "PASS"}, indent=2) + "\n")
    finally: app.close()
    return 0

if __name__ == "__main__": raise SystemExit(main())
