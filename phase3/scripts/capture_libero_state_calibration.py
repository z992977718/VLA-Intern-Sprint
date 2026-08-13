#!/usr/bin/env python3
"""Capture LIBERO state semantics at fixed Panda joint configurations only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from libero.libero import benchmark, get_libero_path
from libero.libero.envs import OffScreenRenderEnv
from lerobot.envs.libero import get_task_init_states

POSES = {
    "reference": [0.012, -0.568, 0.0, -2.811, 0.0, 3.037, 0.741],
    "shoulder_y": [0.35, -0.70, 0.15, -2.50, 0.10, 2.80, 0.60],
    "elbow_z": [-0.35, -0.40, -0.25, -2.45, -0.15, 2.65, 0.80],
    "wrist_roll": [0.10, -0.70, 0.10, -2.60, 0.70, 2.90, 0.65],
    "wrist_yaw": [-0.15, -0.55, -0.10, -2.70, -0.50, 2.40, 0.90],
}
GRIPPERS = {"open": [0.04, -0.04], "intermediate": [0.02, -0.02], "closed": [0.0, 0.0]}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    output = args.output.resolve()
    if output.exists(): raise FileExistsError(f"refusing to overwrite {output}")
    suite = benchmark.get_benchmark_dict()["libero_10"](); task = suite.get_task(0)
    bddl = Path(get_libero_path("bddl_files")) / task.problem_folder / task.bddl_file
    states = np.asarray(get_task_init_states(suite, 0))
    records = []; gripper_records = []
    env = OffScreenRenderEnv(bddl_file_name=str(bddl), control_freq=20, hard_reset=True)
    try:
        for label, joints in POSES.items():
            env.reset(); raw = env.set_init_state(states[0])
            robot = env.robots[0]
            env.sim.data.qpos[robot._ref_joint_pos_indexes] = np.asarray(joints)
            env.sim.forward(); robot.controller.update(force=True)
            raw = env.env._get_observations(force_update=True)
            records.append({"label": label, "joint_positions_rad": joints, "eef_position_xyz_m": np.asarray(raw["robot0_eef_pos"], float).tolist(), "eef_quaternion_xyzw": np.asarray(raw["robot0_eef_quat"], float).tolist(), "controller_ee_orientation_matrix": np.asarray(robot.controller.ee_ori_mat, float).tolist(), "gripper_qpos": np.asarray(raw["robot0_gripper_qpos"], float).tolist(), "eef_observable": "robot0_eef_pos / robot0_eef_quat"})
        env.reset(); raw = env.set_init_state(states[0]); robot = env.robots[0]
        for label, qpos in GRIPPERS.items():
            env.sim.data.qpos[robot._ref_gripper_joint_pos_indexes] = np.asarray(qpos)
            env.sim.forward(); raw = env.env._get_observations(force_update=True)
            gripper_records.append({"label": label, "set_qpos": qpos, "observed_robot0_gripper_qpos": np.asarray(raw["robot0_gripper_qpos"], float).tolist()})
        payload = {"task": task.language, "init_state_id": 0, "control_frequency_hz": 20, "comparison_basis": "same explicit Panda arm joint vector is assigned in LIBERO and Isaac; no task action is executed", "poses": records, "gripper_states": gripper_records, "state_sources": {"position": "raw observation robot0_eef_pos", "orientation": "raw observation robot0_eef_quat (xyzw) plus controller.ee_ori_mat", "gripper": "raw observation robot0_gripper_qpos"}}
        output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(payload, indent=2) + "\n")
    finally: env.close()
    return 0

if __name__ == "__main__": raise SystemExit(main())
