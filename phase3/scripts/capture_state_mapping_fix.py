#!/usr/bin/env python3
"""Capture LIBERO and Isaac static state frames for Step 7B.1 only.

Each mode sets explicit safe Panda joint vectors, reads state frames, and
closes. It does not invoke Pi0.5, actions, IK, task success, or rollout.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np


CALIBRATION_POSES = {
    "reference": [0.012, -0.568, 0.0, -2.811, 0.0, 3.037, 0.741],
    "shoulder_y": [0.35, -0.70, 0.15, -2.50, 0.10, 2.80, 0.60],
    "elbow_z": [-0.35, -0.40, -0.25, -2.45, -0.15, 2.65, 0.80],
    "wrist_roll": [0.10, -0.70, 0.10, -2.60, 0.70, 2.90, 0.65],
    "wrist_yaw": [-0.15, -0.55, -0.10, -2.70, -0.50, 2.40, 0.90],
}
HOLDOUT_POSES = {
    "holdout_a": [0.20, -0.62, -0.10, -2.65, 0.25, 2.70, 0.72],
    "holdout_b": [-0.25, -0.48, 0.22, -2.55, -0.30, 2.88, 0.55],
    "holdout_c": [0.05, -0.82, -0.18, -2.35, 0.45, 2.55, 0.82],
    "holdout_d": [-0.10, -0.60, 0.12, -2.75, -0.42, 2.48, 0.68],
    "holdout_e": [0.28, -0.50, -0.20, -2.72, 0.50, 2.95, 0.50],
}
GRIPPERS_LIBERO = {"open": [0.04, -0.04], "intermediate": [0.02, -0.02], "closed": [0.0, 0.0]}
GRIPPERS_ISAAC = {"open": [0.04, 0.04], "intermediate": [0.02, 0.02], "closed": [0.0, 0.0]}


def capture_libero(poses: dict[str, list[float]]) -> dict:
    from libero.libero import benchmark, get_libero_path
    from libero.libero.envs import OffScreenRenderEnv
    from lerobot.envs.libero import get_task_init_states

    suite = benchmark.get_benchmark_dict()["libero_10"]()
    task = suite.get_task(0)
    bddl = Path(get_libero_path("bddl_files")) / task.problem_folder / task.bddl_file
    states = np.asarray(get_task_init_states(suite, 0))
    env = OffScreenRenderEnv(bddl_file_name=str(bddl), control_freq=20, hard_reset=True)
    records = []
    try:
        for label, joints in poses.items():
            env.reset(); env.set_init_state(states[0])
            robot = env.robots[0]
            env.sim.data.qpos[robot._ref_joint_pos_indexes] = np.asarray(joints)
            env.sim.forward(); robot.controller.update(force=True)
            raw = env.env._get_observations(force_update=True)
            site_id = robot.eef_site_id
            body_id = env.sim.model.body_name2id(robot.robot_model.eef_name)
            records.append({
                "label": label, "joint_positions_rad": joints,
                "grip_site_position_xyz_m": np.asarray(raw["robot0_eef_pos"], float).tolist(),
                "eef_body_quaternion_xyzw": np.asarray(raw["robot0_eef_quat"], float).tolist(),
                "grip_site_name": robot.gripper.important_sites["grip_site"],
                "eef_body_name": robot.robot_model.eef_name,
                "grip_site_id": int(site_id), "eef_body_id": int(body_id),
                "gripper_qpos": np.asarray(raw["robot0_gripper_qpos"], float).tolist(),
            })
        env.reset(); env.set_init_state(states[0]); robot = env.robots[0]
        grippers = []
        for label, qpos in GRIPPERS_LIBERO.items():
            env.sim.data.qpos[robot._ref_gripper_joint_pos_indexes] = qpos
            env.sim.forward(); raw = env.env._get_observations(force_update=True)
            grippers.append({"label": label, "qpos": np.asarray(raw["robot0_gripper_qpos"], float).tolist()})
    finally:
        env.close()
    return {"simulator": "LIBERO", "poses": records, "gripper_states": grippers}


def capture_isaac(poses: dict[str, list[float]], output: Path, pose_set: str) -> None:
    os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
    from isaacsim import SimulationApp
    from isaac_step6_scene_gate import build_scene, prim_world_pose

    app = SimulationApp({"headless": True, "renderer": "RaytracedLighting"})
    try:
        scene = build_scene(app, 0, dynamic_objects=False)
        stage = scene["stage"]
        hand = next(x for x in stage.Traverse() if x.GetName() == "panda_hand")
        tool = next(x for x in stage.Traverse() if x.GetName() == "tool_center")
        records = []
        for label, joints in poses.items():
            q = np.asarray(joints + GRIPPERS_ISAAC["intermediate"], dtype=np.float32)
            scene["robot"].set_dof_positions(q); scene["robot"].set_dof_position_targets(q)
            for _ in range(60): scene["world"].step(render=False)
            hand_position, hand_quaternion = prim_world_pose(stage, scene["Usd"], scene["UsdGeom"], str(hand.GetPath()))
            tool_position, tool_quaternion = prim_world_pose(stage, scene["Usd"], scene["UsdGeom"], str(tool.GetPath()))
            records.append({
                "label": label, "joint_positions_rad": joints,
                "panda_hand_path": str(hand.GetPath()), "panda_hand_position_xyz_m": hand_position.tolist(),
                "panda_hand_quaternion_wxyz": hand_quaternion.tolist(),
                "tool_center_path": str(tool.GetPath()), "tool_center_position_xyz_m": tool_position.tolist(),
                "tool_center_quaternion_wxyz": tool_quaternion.tolist(),
                "finger_qpos": scene["robot"].get_dof_positions().numpy()[0, 7:].tolist(),
            })
        grippers = []
        for label, qpos in GRIPPERS_ISAAC.items():
            q = scene["robot"].get_dof_positions().numpy()[0].copy(); q[7:] = qpos
            scene["robot"].set_dof_positions(q.astype(np.float32)); scene["robot"].set_dof_position_targets(q.astype(np.float32))
            for _ in range(30): scene["world"].step(render=False)
            grippers.append({"label": label, "qpos": scene["robot"].get_dof_positions().numpy()[0, 7:].tolist()})
        # Isaac SimulationApp.close() terminates its embedded runtime. Persist
        # the capture before close, rather than returning it to main().
        payload = {
            "simulator": "Isaac", "poses": records, "gripper_states": grippers,
            "set": pose_set,
            "comparison_basis": "same explicit Panda joint vectors; no task action, policy, or rollout",
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    finally:
        app.close()
    return {"simulator": "Isaac", "poses": records, "gripper_states": grippers}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("libero", "isaac"), required=True)
    parser.add_argument("--set", choices=("calibration", "holdout"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    poses = CALIBRATION_POSES if args.set == "calibration" else HOLDOUT_POSES
    if args.mode == "isaac":
        capture_isaac(poses, args.output, args.set)
        return 0
    payload = capture_libero(poses)
    payload.update({"set": args.set, "comparison_basis": "same explicit Panda joint vectors; no task action, policy, or rollout"})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
