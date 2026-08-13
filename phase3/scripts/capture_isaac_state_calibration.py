#!/usr/bin/env python3
"""Capture static Isaac Panda hand/tool poses at five fixed configurations only."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
from isaacsim import SimulationApp

from isaac_step6_scene_gate import build_scene, prim_world_pose
from phase3_step6_common import EEF_OFFSET_IN_HAND_M, quaternion_wxyz_to_matrix

POSES = {
    "reference": [0.012, -0.568, 0.0, -2.811, 0.0, 3.037, 0.741],
    "shoulder_y": [0.35, -0.70, 0.15, -2.50, 0.10, 2.80, 0.60],
    "elbow_z": [-0.35, -0.40, -0.25, -2.45, -0.15, 2.65, 0.80],
    "wrist_roll": [0.10, -0.70, 0.10, -2.60, 0.70, 2.90, 0.65],
    "wrist_yaw": [-0.15, -0.55, -0.10, -2.70, -0.50, 2.40, 0.90],
}
GRIPPERS = {"open": [0.04, 0.04], "intermediate": [0.02, 0.02], "closed": [0.0, 0.0]}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    output = args.output.resolve()
    if output.exists(): raise FileExistsError(f"refusing to overwrite {output}")
    app = SimulationApp({"headless": True, "renderer": "RaytracedLighting"})
    try:
        scene = build_scene(app, 0, dynamic_objects=False); robot, stage = scene["robot"], scene["stage"]
        hand = next(p for p in stage.Traverse() if p.GetName() == "panda_hand"); hand_path = str(hand.GetPath())
        records = []
        for label, joints in POSES.items():
            q = np.asarray(joints + GRIPPERS["intermediate"], np.float32)
            robot.set_dof_positions(q); robot.set_dof_position_targets(q)
            for _ in range(60): scene["world"].step(render=False)
            position, quat = prim_world_pose(stage, scene["Usd"], scene["UsdGeom"], hand_path); rotation = quaternion_wxyz_to_matrix(quat)
            tool = position + rotation @ EEF_OFFSET_IN_HAND_M
            records.append({"label": label, "joint_positions_rad": joints, "panda_hand_position_xyz_m": position.tolist(), "panda_hand_quaternion_wxyz": quat.tolist(), "panda_hand_rotation_matrix": rotation.tolist(), "tool_offset_local_m": EEF_OFFSET_IN_HAND_M.tolist(), "tool_offset_world_m": (rotation @ EEF_OFFSET_IN_HAND_M).tolist(), "current_tool_point_xyz_m": tool.tolist(), "current_tool_orientation_matrix": rotation.tolist(), "finger_qpos": robot.get_dof_positions().numpy()[0, 7:].tolist()})
        gripper = []
        for label, fingers in GRIPPERS.items():
            q = robot.get_dof_positions().numpy()[0].copy(); q[7:] = np.asarray(fingers)
            robot.set_dof_positions(q.astype(np.float32)); robot.set_dof_position_targets(q.astype(np.float32))
            for _ in range(30): scene["world"].step(render=False)
            gripper.append({"label": label, "set_qpos": fingers, "observed_finger_qpos": robot.get_dof_positions().numpy()[0, 7:].tolist()})
        payload = {"comparison_basis": "same explicit Panda arm joint vector is assigned in LIBERO and Isaac; no task action is executed", "poses": records, "gripper_states": gripper, "state_sources": {"position": "USD /World panda_hand pose plus R_hand @ [0,0,0.0951034858]", "orientation": "USD /World panda_hand quaternion wxyz, converted to xyzw before LiberoProcessorStep", "gripper": "panda_finger_joint1, panda_finger_joint2 DOF positions"}}
        output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(payload, indent=2) + "\n")
    finally: app.close()
    return 0

if __name__ == "__main__": raise SystemExit(main())
