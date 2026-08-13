#!/usr/bin/env python3
"""Offline-only Step 7B.1 comparison of captured static state frames."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


OLD_OFFSET = np.array([0.0, 0.0, 0.0951034858], dtype=float)


def quaternion_wxyz_to_matrix(quaternion: list[float]) -> np.ndarray:
    w, x, y, z = np.asarray(quaternion, dtype=float)
    w, x, y, z = np.asarray([w, x, y, z], dtype=float) / np.linalg.norm([w, x, y, z])
    return np.array([
        [1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w)],
        [2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w)],
        [2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y)],
    ])


def quaternion_xyzw_to_matrix(quaternion: list[float]) -> np.ndarray:
    x, y, z, w = np.asarray(quaternion, dtype=float)
    return quaternion_wxyz_to_matrix([w, x, y, z])


def angle(rotation: np.ndarray) -> float:
    return float(math.acos(float(np.clip((np.trace(rotation) - 1.0) / 2.0, -1.0, 1.0))))


def summary(values: list[float]) -> dict:
    return {"mean": float(np.mean(values)), "max": float(np.max(values)), "min": float(np.min(values))}


def compare(libero: dict, isaac: dict) -> dict:
    left = {x["label"]: x for x in libero["poses"]}
    right = {x["label"]: x for x in isaac["poses"]}
    if list(left) != list(right):
        raise ValueError("pose labels differ")
    rows = []
    for label in left:
        l, r = left[label], right[label]
        if l["joint_positions_rad"] != r["joint_positions_rad"]:
            raise ValueError(f"joint mismatch at {label}")
        hand = np.asarray(r["panda_hand_position_xyz_m"], float)
        hand_r = quaternion_wxyz_to_matrix(r["panda_hand_quaternion_wxyz"])
        old = hand + hand_r @ OLD_OFFSET
        tool = np.asarray(r["tool_center_position_xyz_m"], float)
        libero_pos = np.asarray(l["grip_site_position_xyz_m"], float)
        libero_r = quaternion_xyzw_to_matrix(l["eef_body_quaternion_xyzw"])
        rows.append({
            "label": label,
            "joint_positions_rad": l["joint_positions_rad"],
            "libero_grip_site_xyz_m": libero_pos.tolist(),
            "old_adapter_xyz_m": old.tolist(),
            "isaac_tool_center_xyz_m": tool.tolist(),
            "old_position_error_m": float(np.linalg.norm(old - libero_pos)),
            "tool_center_position_error_m": float(np.linalg.norm(tool - libero_pos)),
            "orientation_error_hand_to_libero_eef_body_rad": angle(hand_r.T @ libero_r),
            "libero_gripper_qpos": l["gripper_qpos"],
            "isaac_finger_qpos": r["finger_qpos"],
        })
    return {
        "rows": rows,
        "old_position_error_m": summary([x["old_position_error_m"] for x in rows]),
        "tool_center_position_error_m": summary([x["tool_center_position_error_m"] for x in rows]),
        "orientation_error_rad": summary([x["orientation_error_hand_to_libero_eef_body_rad"] for x in rows]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir
    names = ["calibration_5_pose_before_after.json", "holdout_5_pose_validation.json", "position_error_summary.json"]
    if any((output / name).exists() for name in names):
        raise FileExistsError("refusing to overwrite completed analysis")
    read = lambda name: json.loads((args.input_dir / name).read_text(encoding="utf-8"))
    calibration = compare(read("libero_calibration.json"), read("isaac_calibration.json"))
    holdout = compare(read("libero_holdout.json"), read("isaac_holdout.json"))
    output.mkdir(parents=True, exist_ok=True)
    (output / "calibration_5_pose_before_after.json").write_text(json.dumps(calibration, indent=2) + "\n", encoding="utf-8")
    (output / "holdout_5_pose_validation.json").write_text(json.dumps(holdout, indent=2) + "\n", encoding="utf-8")
    position = {
        "old_adapter": "p_hand + R_hand @ [0,0,0.0951034858]",
        "candidate_after": "USD /World/Robot/panda_hand/tool_center world pose",
        "calibration_before_m": calibration["old_position_error_m"],
        "calibration_after_m": calibration["tool_center_position_error_m"],
        "holdout_before_m": holdout["old_position_error_m"],
        "holdout_after_m": holdout["tool_center_position_error_m"],
        "candidate_improves_calibration": calibration["tool_center_position_error_m"]["mean"] < calibration["old_position_error_m"]["mean"],
        "candidate_improves_holdout": holdout["tool_center_position_error_m"]["mean"] < holdout["old_position_error_m"]["mean"],
    }
    (output / "position_error_summary.json").write_text(json.dumps(position, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
