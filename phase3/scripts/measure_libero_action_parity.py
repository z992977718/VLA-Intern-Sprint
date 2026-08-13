#!/usr/bin/env python3
"""Measure one real LIBERO control step for each Step 7A canonical action."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from libero.libero import benchmark, get_libero_path
from libero.libero.envs import OffScreenRenderEnv
from lerobot.envs.libero import get_task_init_states


CASES = {
    "+X": [0.10, 0, 0, 0, 0, 0, 0], "-X": [-0.10, 0, 0, 0, 0, 0, 0],
    "+Y": [0, 0.10, 0, 0, 0, 0, 0], "-Y": [0, -0.10, 0, 0, 0, 0, 0],
    "+Z": [0, 0, 0.10, 0, 0, 0, 0], "-Z": [0, 0, -0.10, 0, 0, 0, 0],
    "+Rx": [0, 0, 0, 0.05, 0, 0, 0], "-Rx": [0, 0, 0, -0.05, 0, 0, 0],
    "+Ry": [0, 0, 0, 0, 0.05, 0, 0], "-Ry": [0, 0, 0, 0, -0.05, 0, 0],
    "+Rz": [0, 0, 0, 0, 0, 0.05, 0], "-Rz": [0, 0, 0, 0, 0, -0.05, 0],
    "open": [0, 0, 0, 0, 0, 0, -1], "close": [0, 0, 0, 0, 0, 0, 1],
}


def matrix_axis_angle(matrix: np.ndarray) -> list[float]:
    angle = float(np.arccos(np.clip((np.trace(matrix) - 1.0) / 2.0, -1.0, 1.0)))
    if angle < 1e-9:
        return [0.0, 0.0, 0.0]
    axis = np.array([matrix[2, 1] - matrix[1, 2], matrix[0, 2] - matrix[2, 0], matrix[1, 0] - matrix[0, 1]])
    return (axis / (2.0 * np.sin(angle)) * angle).tolist()


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    suite = benchmark.get_benchmark_dict()["libero_10"]()
    task = suite.get_task(0)
    states = np.asarray(get_task_init_states(suite, 0))
    bddl = Path(get_libero_path("bddl_files")) / task.problem_folder / task.bddl_file
    results: dict[str, dict] = {}
    for name, values in CASES.items():
        env = OffScreenRenderEnv(bddl_file_name=str(bddl), camera_names=["agentview", "robot0_eye_in_hand"], camera_heights=64, camera_widths=64, control_freq=20, hard_reset=True)
        try:
            env.reset(); raw = env.set_init_state(states[0])
            for _ in range(10): raw, _, _, _ = env.step([0, 0, 0, 0, 0, 0, -1])
            robot = env.robots[0]
            pos_before = np.asarray(raw["robot0_eef_pos"], dtype=float)
            rot_before = np.asarray(robot.controller.ee_ori_mat, dtype=float)
            grip_before = np.asarray(raw["robot0_gripper_qpos"], dtype=float)
            raw, _, _, _ = env.step(np.asarray(values, dtype=np.float32))
            pos_after = np.asarray(raw["robot0_eef_pos"], dtype=float)
            rot_after = np.asarray(robot.controller.ee_ori_mat, dtype=float)
            grip_after = np.asarray(raw["robot0_gripper_qpos"], dtype=float)
            relative = rot_after @ rot_before.T
            results[name] = {
                "raw_normalized_action": values, "independent_hard_reset": True,
                "control_frequency_hz": 20, "control_duration_sec": 0.05,
                "controller_goal_position_xyz_m": np.asarray(robot.controller.goal_pos, dtype=float).tolist(),
                "controller_goal_orientation_matrix": np.asarray(robot.controller.goal_ori, dtype=float).tolist(),
                "eef_before_xyz_m": pos_before.tolist(), "eef_after_xyz_m": pos_after.tolist(),
                "actual_delta_xyz_m": (pos_after - pos_before).tolist(), "actual_displacement_m": float(np.linalg.norm(pos_after - pos_before)),
                "rotation_before_matrix": rot_before.tolist(), "rotation_after_matrix": rot_after.tolist(),
                "relative_rotation_axis_angle_rad": matrix_axis_angle(relative),
                "gripper_before_qpos": grip_before.tolist(), "gripper_after_qpos": grip_after.tolist(),
                "gripper_semantic": "OPEN" if values[6] < 0 else ("CLOSED" if values[6] > 0 else "HOLD"),
            }
        finally:
            env.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"protocol": "one OffScreenRenderEnv.step per action after independent hard reset and ten no-op settle steps", "cases": results}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
