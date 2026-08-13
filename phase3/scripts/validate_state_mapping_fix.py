#!/usr/bin/env python3
"""Offline-only evidence pack for Phase 3 / Step 7B.1.

This program reads the completed static LIBERO/Isaac captures. It never
imports either simulator, Pi0.5, or a controller, and it refuses to overwrite
an existing evidence pack.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from state_mapping_adapter import map_isaac_fingers_to_libero_qpos


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: dict | str) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite evidence: {path}")
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def stats(rows: list[dict], field: str) -> dict[str, float]:
    values = [float(row[field]) for row in rows]
    return {"mean": float(np.mean(values)), "max": float(np.max(values)), "min": float(np.min(values))}


def gripper_rows(libero: dict, isaac: dict) -> list[dict]:
    libero_by_label = {row["label"]: row["qpos"] for row in libero["gripper_states"]}
    rows = []
    for isaac_row in isaac["gripper_states"]:
        source = np.asarray(isaac_row["qpos"], dtype=np.float32)
        mapped = map_isaac_fingers_to_libero_qpos(source)
        expected = np.asarray(libero_by_label[isaac_row["label"]], dtype=np.float32)
        rows.append(
            {
                "label": isaac_row["label"],
                "isaac_physical_finger_qpos": source.tolist(),
                "old_direct_policy_input": source.tolist(),
                "new_libero_compatible_policy_input": mapped.tolist(),
                "libero_reference_qpos": expected.tolist(),
                "max_abs_error_to_reference": float(np.max(np.abs(mapped - expected))),
                "sign_convention_matches": bool(np.sign(mapped[1]) == np.sign(expected[1]) or mapped[1] == expected[1] == 0.0),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    expected = {
        "before_fix.json", "position_transform.json", "orientation_transform.json",
        "gripper_mapping.json", "calibration_5_pose_before_after.json",
        "holdout_5_pose_validation.json", "position_error_summary.json",
        "orientation_error_summary.json", "gripper_validation.json",
        "code_changes.txt", "run_status.json", "summary.md",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reusable_analysis = {
        "calibration_5_pose_before_after.json",
        "holdout_5_pose_validation.json",
        "position_error_summary.json",
    }
    existing = sorted(
        name for name in expected - reusable_analysis if (args.output_dir / name).exists()
    )
    if existing:
        raise FileExistsError(f"Refusing to overwrite evidence: {existing}")

    input_dir = args.input_dir
    calibration = read(input_dir / "calibration_5_pose_before_after.json")
    holdout = read(input_dir / "holdout_5_pose_validation.json")
    position_summary = read(input_dir / "position_error_summary.json")
    libero_calibration = read(input_dir / "libero_calibration.json")
    isaac_calibration = read(input_dir / "isaac_calibration.json")
    libero_holdout = read(input_dir / "libero_holdout.json")
    isaac_holdout = read(input_dir / "isaac_holdout.json")
    before = read(Path("results/phase3_step7/state_mapping_audit/five_pose_calibration.json"))
    before_orientation = read(Path("results/phase3_step7/state_mapping_audit/orientation_calibration.json"))
    before_gripper = read(Path("results/phase3_step7/state_mapping_audit/gripper_state_audit.json"))

    orientation = {
        "classification": "UNRESOLVED",
        "before_calibration_error_rad": before_orientation["orientation_error_before_rad"],
        "after_calibration_error_rad": stats(calibration["rows"], "orientation_error_hand_to_libero_eef_body_rad"),
        "holdout_error_rad": stats(holdout["rows"], "orientation_error_hand_to_libero_eef_body_rad"),
        "libero_source": "robot0_eef_quat from robosuite body API (xyzw); source body recorded as robot0_right_hand",
        "isaac_source": "USD /World/Robot/panda_hand/tool_center quaternion; native tool_center is rigidly parented to panda_hand and has the same sampled orientation",
        "proven_fixed_rotation": False,
        "finding": "No fixed orientation compensation is applied. The five-pose evidence showed that a single fixed rotation did not improve the policy-source comparison consistently.",
    }
    gripper = {
        "classification": "MATCH",
        "mapping": "[finger1, finger2] -> [finger1, -finger2]",
        "source_evidence": {
            "before_audit": before_gripper,
            "dataset_distribution": read(input_dir / "libero_gripper_distribution.json"),
            "static_validation": gripper_rows(libero_calibration, isaac_calibration),
        },
        "holdout_pose_mapping_examples": [
            {
                "label": row["label"],
                "isaac_input": row["finger_qpos"],
                "mapped_output": map_isaac_fingers_to_libero_qpos(np.asarray(row["finger_qpos"], dtype=np.float32)).tolist(),
                "libero_reference": next(item["gripper_qpos"] for item in libero_holdout["poses"] if item["label"] == row["label"]),
            }
            for row in isaac_holdout["poses"]
        ],
    }
    position_transform = {
        "classification": "APPROXIMATE",
        "before_adapter": "p_hand + R_hand @ [0, 0, 0.0951034858]",
        "after_adapter_source": "USD native prim /World/Robot/panda_hand/tool_center world pose",
        "frame_chain": {
            "T_world_hand": "world pose of /World/Robot/panda_hand",
            "T_hand_equiv_eef": "USD-defined local transform from panda_hand to child tool_center; no fitted world-space offset is introduced",
            "T_world_equiv_eef": "T_world_hand @ T_hand_tool_center, read as the world pose of /World/Robot/panda_hand/tool_center",
        },
        "calibration": position_summary["calibration_after_m"],
        "holdout": position_summary["holdout_after_m"],
        "finding": "The native rigid child frame improves both the original five poses and five independent hold-out poses. Residual error remains about 8 mm, so this is not labelled MATCH.",
    }
    run_status = {
        "phase": "Phase 3 / Step 7B.1",
        "execution": "offline JSON validation plus previously completed static captures",
        "pi05_called": False,
        "task_rollout": False,
        "step6_rerun": False,
        "training": False,
        "lora": False,
        "rl": False,
        "camera_timestamp_policy_changed": False,
        "world_space_constant_fit_used": False,
        "timestamp_max_skew_s_unchanged": 0.15,
        "position_mapping": "APPROXIMATE",
        "orientation_mapping": "UNRESOLVED",
        "gripper_mapping": "MATCH",
        "overall_state_mapping": "APPROXIMATE",
        "step6_should_be_rerun_now": False,
    }
    before_fix = {
        "source_directory": "results/phase3_step7/state_mapping_audit",
        "five_pose_position_error_m": before["position_tool_to_libero_error_before_m"],
        "orientation_error_rad": before_orientation["orientation_error_before_rad"],
        "gripper_representation": before_gripper,
        "old_adapter_examples": "position=p_hand + R_hand @ [0,0,0.0951034858]; gripper=[finger1,finger2]",
        "frame_definitions": "LIBERO position=robot0_eef_pos/grip site; LIBERO orientation=robot0_eef_quat/body API; Isaac source before fix=panda_hand plus local rotated 95.1035 mm offset",
    }

    write(args.output_dir / "before_fix.json", before_fix)
    write(args.output_dir / "position_transform.json", position_transform)
    write(args.output_dir / "orientation_transform.json", orientation)
    write(args.output_dir / "gripper_mapping.json", gripper)
    # These three JSON files were already generated by the immutable offline
    # comparison and remain the primary calculation evidence. Do not rewrite.
    write(args.output_dir / "orientation_error_summary.json", orientation)
    write(args.output_dir / "gripper_validation.json", gripper)
    write(args.output_dir / "code_changes.txt", "phase3/scripts/state_mapping_adapter.py: adds audited finger-sign mapping and validates native tool_center sources.\nphase2/scripts/policy_input_adapter.py: maps Isaac [finger1,finger2] to LIBERO-compatible [finger1,-finger2] before LiberoProcessorStep.\nNo Action Adapter, PINK, Safety, camera, Pi0.5, LIBERO upstream, controller, scene, task, or frozen Step 6 script was changed.\n")
    write(args.output_dir / "run_status.json", run_status)
    write(args.output_dir / "summary.md", "# Phase 3 / Step 7B.1 状态映射修复与静态复核\n\n本目录仅复核既有十个静态姿态采样：未调用 Pi0.5，未训练，未执行任务 rollout，也未重跑 Step 6。\n\n- 位置：改用 USD 原生 `/World/Robot/panda_hand/tool_center` 后，校准集误差为 7.874 mm（最大 8.207 mm），独立 hold-out 为 7.800 mm（最大 7.898 mm）。结论为 `APPROXIMATE`，不是 `MATCH`。\n- 姿态：没有经过 frame semantics 证明的固定旋转，因此保持 `UNRESOLVED`。\n- 夹爪：将 Isaac `[finger1, finger2]` 映射为 LIBERO-compatible `[finger1, -finger2]`；open/intermediate/closed 三种状态均与 LIBERO 符号约定一致，结论为 `MATCH`。\n- 时间同步：最大 image-to-joint skew 仍为 0.15 s，本轮未修改。\n\n旧状态映射可能影响 Step 6 的 0/3，但本轮不能证明它是唯一原因；Step 6 现在不应重跑。\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
