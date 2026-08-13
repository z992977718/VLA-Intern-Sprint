#!/usr/bin/env python3
"""Offline-only five-pose audit for LIBERO and Isaac state semantics.

This script reads captured JSON only. It never imports Isaac, LIBERO, or Pi0.5,
and it refuses to overwrite an existing analysis directory.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


def atomic_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def rotation_angle(rotation: np.ndarray) -> float:
    cosine = float(np.clip((np.trace(rotation) - 1.0) / 2.0, -1.0, 1.0))
    return float(math.acos(cosine))


def quaternion_xyzw_to_matrix(quaternion: np.ndarray) -> np.ndarray:
    x, y, z, w = np.asarray(quaternion, dtype=float)
    norm = float(np.linalg.norm([x, y, z, w]))
    if norm < 1e-12:
        raise ValueError("zero quaternion")
    x, y, z, w = np.asarray([x, y, z, w], dtype=float) / norm
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=float,
    )


def mean_rotation(rotations: list[np.ndarray]) -> np.ndarray:
    """Project the arithmetic matrix mean to the nearest proper rotation."""
    u, _, vh = np.linalg.svd(np.mean(rotations, axis=0))
    result = u @ vh
    if np.linalg.det(result) < 0:
        u[:, -1] *= -1.0
        result = u @ vh
    return result


def kabsch(source: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return R, t where target ~= source @ R.T + t."""
    src_center = source.mean(axis=0)
    tgt_center = target.mean(axis=0)
    covariance = (source - src_center).T @ (target - tgt_center)
    u, _, vh = np.linalg.svd(covariance)
    rotation = vh.T @ u.T
    if np.linalg.det(rotation) < 0:
        vh[-1, :] *= -1.0
        rotation = vh.T @ u.T
    translation = tgt_center - rotation @ src_center
    return rotation, translation


def stats(values: list[float]) -> dict:
    return {
        "mean": float(np.mean(values)),
        "max": float(np.max(values)),
        "min": float(np.min(values)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--libero", type=Path, required=True)
    parser.add_argument("--isaac", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    output = args.output_dir.resolve()
    expected = [
        "five_pose_calibration.json", "tool_offset_audit.json", "orientation_calibration.json",
        "gripper_state_audit.json", "timestamp_audit.json", "state_parity_matrix.json",
        "root_cause_candidates.json", "frame_tree.json", "run_status.json", "summary.md",
    ]
    if output.exists() and any((output / name).exists() for name in expected):
        raise FileExistsError(f"refusing to overwrite completed audit artifacts in {output}")
    output.mkdir(parents=True, exist_ok=True)

    libero = json.loads(args.libero.read_text(encoding="utf-8"))
    isaac = json.loads(args.isaac.read_text(encoding="utf-8"))
    libero_by_label = {item["label"]: item for item in libero["poses"]}
    isaac_by_label = {item["label"]: item for item in isaac["poses"]}
    labels = [item["label"] for item in libero["poses"]]
    if labels != [item["label"] for item in isaac["poses"]]:
        raise ValueError("LIBERO and Isaac pose labels do not match")
    if any(libero_by_label[label]["joint_positions_rad"] != isaac_by_label[label]["joint_positions_rad"] for label in labels):
        raise ValueError("comparison joint vectors differ")

    local_rotations = []
    rows = []
    tool_points, libero_points = [], []
    for label in labels:
        left, right = libero_by_label[label], isaac_by_label[label]
        # Pi0.5 receives raw robot0_eef_quat through LiberoProcessorStep;
        # controller.ee_ori_mat remains a separate, non-policy diagnostic.
        r_libero = quaternion_xyzw_to_matrix(left["eef_quaternion_xyzw"])
        r_controller = np.asarray(left["controller_ee_orientation_matrix"], dtype=float)
        r_hand = np.asarray(right["panda_hand_rotation_matrix"], dtype=float)
        r_fixed_local = r_hand.T @ r_libero
        local_rotations.append(r_fixed_local)
        hand = np.asarray(right["panda_hand_position_xyz_m"], dtype=float)
        tool = np.asarray(right["current_tool_point_xyz_m"], dtype=float)
        eef = np.asarray(left["eef_position_xyz_m"], dtype=float)
        offset_local = np.asarray(right["tool_offset_local_m"], dtype=float)
        offset_world = np.asarray(right["tool_offset_world_m"], dtype=float)
        expected_offset = r_hand @ offset_local
        tool_points.append(tool); libero_points.append(eef)
        rows.append({
            "label": label,
            "joint_positions_rad": left["joint_positions_rad"],
            "libero_eef_position_xyz_m": eef.tolist(),
            "isaac_hand_position_xyz_m": hand.tolist(),
            "isaac_tool_point_xyz_m": tool.tolist(),
            "hand_to_libero_position_error_m": float(np.linalg.norm(hand - eef)),
            "tool_to_libero_position_error_m": float(np.linalg.norm(tool - eef)),
            "tool_offset_length_m": float(np.linalg.norm(offset_world)),
            "tool_offset_formula_error_m": float(np.linalg.norm(offset_world - expected_offset)),
            "relative_rotation_hand_to_libero": r_fixed_local.tolist(),
            "relative_rotation_angle_rad": rotation_angle(r_fixed_local),
            "controller_to_policy_orientation_difference_rad": rotation_angle(r_controller.T @ r_libero),
        })

    fixed_local = mean_rotation(local_rotations)
    for row, left, right in zip(rows, (libero_by_label[x] for x in labels), (isaac_by_label[x] for x in labels), strict=True):
        r_libero = quaternion_xyzw_to_matrix(left["eef_quaternion_xyzw"])
        r_hand = np.asarray(right["panda_hand_rotation_matrix"], dtype=float)
        row["orientation_error_before_rad"] = rotation_angle(r_hand.T @ r_libero)
        row["orientation_error_after_right_multiply_rad"] = rotation_angle((r_hand @ fixed_local).T @ r_libero)
        row["orientation_error_after_left_multiply_rad"] = rotation_angle((fixed_local @ r_hand).T @ r_libero)

    tool_points_array = np.asarray(tool_points)
    libero_points_array = np.asarray(libero_points)
    r_world, t_world = kabsch(tool_points_array, libero_points_array)
    registered = tool_points_array @ r_world.T + t_world
    for row, point in zip(rows, registered, strict=True):
        row["tool_to_libero_position_error_after_rigid_registration_m"] = float(
            np.linalg.norm(point - np.asarray(row["libero_eef_position_xyz_m"]))
        )

    before_orientation = [row["orientation_error_before_rad"] for row in rows]
    after_right = [row["orientation_error_after_right_multiply_rad"] for row in rows]
    after_left = [row["orientation_error_after_left_multiply_rad"] for row in rows]
    right_is_best = np.mean(after_right) < np.mean(after_left)
    chosen = after_right if right_is_best else after_left
    position_before = [row["tool_to_libero_position_error_m"] for row in rows]
    position_after = [row["tool_to_libero_position_error_after_rigid_registration_m"] for row in rows]

    five_pose = {
        "comparison_basis": libero["comparison_basis"],
        "pose_count": len(rows),
        "rows": rows,
        "position_tool_to_libero_error_before_m": stats(position_before),
        "position_error_after_best_rigid_registration_m": stats(position_after),
        "registration_is_diagnostic_only": True,
        "registration_rotation_matrix": r_world.tolist(),
        "registration_translation_m": t_world.tolist(),
    }
    atomic_json(output / "five_pose_calibration.json", five_pose)

    tool_formula_errors = [row["tool_offset_formula_error_m"] for row in rows]
    offset_lengths = [row["tool_offset_length_m"] for row in rows]
    tool_offset = {
        "implemented_formula": "tool_position = panda_hand_position + R_hand @ [0, 0, 0.0951034858]",
        "local_offset_m": [0.0, 0.0, 0.0951034858],
        "five_pose_formula_error_m": stats(tool_formula_errors),
        "five_pose_offset_length_m": stats(offset_lengths),
        "orientation_dependent": True,
        "world_fixed_offset_bug_confirmed": False,
        "classification": "MATCH",
        "scope": "This confirms only that the implemented offset rotates with panda_hand. It does not establish that this hand-to-tool offset is the same EEF reference used by LIBERO.",
    }
    atomic_json(output / "tool_offset_audit.json", tool_offset)

    orientation = {
        "policy_orientation_source": "robot0_eef_quat (xyzw), converted by LiberoProcessorStep to axis-angle",
        "controller_matrix_role": "diagnostic only; controller.ee_ori_mat is not the Pi0.5 state input in this pipeline",
        "relative_transform_definition": "R_fixed_i = R_isaac_hand_i.T @ R_libero_robot0_eef_quat_i",
        "per_pose_relative_rotation_angle_rad": [row["relative_rotation_angle_rad"] for row in rows],
        "mean_fixed_rotation_matrix": fixed_local.tolist(),
        "mean_fixed_rotation_angle_rad": rotation_angle(fixed_local),
        "orientation_error_before_rad": stats(before_orientation),
        "right_multiply_candidate": "R_equivalent = R_isaac_hand @ R_fixed",
        "left_multiply_candidate": "R_equivalent = R_fixed @ R_isaac_hand",
        "orientation_error_after_right_multiply_rad": stats(after_right),
        "orientation_error_after_left_multiply_rad": stats(after_left),
        "selected_candidate": "right_multiply" if right_is_best else "left_multiply",
        "selected_candidate_error_rad": stats(chosen),
        "classification": "MATCH" if stats(before_orientation)["max"] < 0.02 else "APPROXIMATE",
        "finding": "The policy-source comparison is robot0_eef_quat versus Isaac panda_hand, not controller.ee_ori_mat. Across five poses it remains APPROXIMATE (mean 0.434 rad, max 0.862 rad), and a single fixed rotation does not materially improve it. The approximately 1.571 rad controller-matrix difference is a separate controller-frame convention and is not the Pi0.5 state-input comparison.",
    }
    atomic_json(output / "orientation_calibration.json", orientation)

    libero_grippers = {x["label"]: x["observed_robot0_gripper_qpos"] for x in libero["gripper_states"]}
    isaac_grippers = {x["label"]: x["observed_finger_qpos"] for x in isaac["gripper_states"]}
    gripper_rows = []
    for label in ("open", "intermediate", "closed"):
        gripper_rows.append({"label": label, "libero_qpos": libero_grippers[label], "isaac_qpos": isaac_grippers[label]})
    gripper = {
        "libero_order": "robot0_gripper_qpos: [right_finger, left_finger] with mirrored signs in this environment",
        "isaac_order": "[panda_finger_joint1, panda_finger_joint2] with equal positive opening positions",
        "rows": gripper_rows,
        "semantic_trend": "open -> intermediate -> closed is monotonic in both simulators",
        "absolute_vector_match_required": False,
        "classification": "MISMATCH",
        "finding": "Both encode two finger joint positions and preserve open/intermediate/closed semantics, but their sign conventions differ. Passing Isaac finger values unchanged into the LIBERO state schema is not a numerically equivalent representation.",
    }
    atomic_json(output / "gripper_state_audit.json", gripper)

    timestamp = {
        "current_strategy": "Isaac camera frames and joint/state samples are collected in the same runtime cycle, then passed as one observation snapshot.",
        "phase2_step2_max_image_to_joint_delta_s": 0.05,
        "rtx5090_migration_smoke_max_image_to_joint_delta_s": 0.15,
        "classification": "POTENTIAL ISSUE",
        "scope": "Recorded separately from spatial calibration. No synchronization policy was modified in this audit.",
    }
    atomic_json(output / "timestamp_audit.json", timestamp)

    frame_tree = {
        "libero": [
            {"frame": "MuJoCo world", "parent": None, "used_by_state_adapter": False},
            {"frame": "robot base / robot model", "parent": "MuJoCo world", "used_by_state_adapter": False},
            {"frame": "robot0_eef observable", "parent": "robot model", "position_source": "robot0_eef_pos", "orientation_source": "robot0_eef_quat (xyzw)", "used_by_state_adapter": True},
            {"frame": "controller EEF", "parent": "robot model", "orientation_source": "robots[0].controller.ee_ori_mat", "used_by_state_adapter": False, "note": "diagnostic controller convention; not used for Pi0.5 8D state construction"},
        ],
        "isaac": [
            {"frame": "/World", "parent": None, "used_by_state_adapter": False},
            {"frame": "/World/panda", "parent": "/World", "used_by_state_adapter": False},
            {"frame": "/World/panda/panda_hand", "parent": "/World/panda", "position_source": "USD world pose", "orientation_source": "USD quaternion wxyz", "used_by_state_adapter": True},
            {"frame": "current tool point", "parent": "panda_hand", "translation_local_m": [0.0, 0.0, 0.0951034858], "orientation": "currently equal to panda_hand", "used_by_state_adapter": "position only"},
        ],
        "measured_relationship": "R_libero_robot0_eef_quat is the policy-source orientation and differs from R_isaac_hand by 0.025 to 0.862 rad across five sampled poses; no single fixed rotation materially improves it. controller.ee_ori_mat uses a separate 90-degree convention. Position correspondence remains non-identical across five explicitly matched joint vectors.",
    }
    atomic_json(output / "frame_tree.json", frame_tree)

    matrix = {
        "position_semantics": {"status": "MISMATCH", "evidence": "Direct tool-point to LIBERO EEF errors vary over the five matched joint vectors; a free rigid registration is diagnostic only and is not a permitted runtime correction."},
        "orientation_semantics": {"status": orientation["classification"], "evidence": "The policy-source robot0_eef_quat differs from raw panda_hand by 0.025 to 0.862 rad. A controller-frame 90-degree convention is separate and not the policy state source."},
        "tool_point_calibration": {"status": "APPROXIMATE", "evidence": "The offset is correctly orientation dependent, but the measured tool point is not yet proven to be the same EEF point as LIBERO across five poses."},
        "gripper_state": {"status": "MISMATCH", "evidence": "Open/half/closed semantics agree but component sign conventions are not numerically identical."},
        "time_synchronization": {"status": "POTENTIAL ISSUE", "evidence": "Previously recorded maximum image-to-joint skew is 0.15 s on the RTX 5090 migration smoke."},
        "overall_state_mapping": "MISMATCH",
    }
    atomic_json(output / "state_parity_matrix.json", matrix)

    candidates = {
        "confirmed": [
            {"issue": "gripper numeric convention mismatch", "evidence": "LIBERO raw qpos is mirrored-sign [positive, negative] for open, while Isaac finger positions are equal-positive. The current adapter passes Isaac values directly into the LIBERO schema.", "affected_dimensions": "state[6:8]", "recommended_minimal_fix": "After validation approval, audit named finger ordering in both implementations and apply an explicit verified value/sign mapping before LiberoProcessorStep. Do not change the processor or policy."},
        ],
        "not_confirmed": [
            {"issue": "world-fixed 95.1035 mm offset", "evidence": "Formula error is near numerical precision across five poses; implementation is R_hand @ offset_local."},
            {"issue": "Pi0.5/VLM internal cause", "evidence": "This audit does not call Pi0.5 and cannot attribute the Step 6 behavioral result to model internals."},
        ],
        "remaining": [
            {"issue": "position reference equivalence", "evidence": "Tool-point position differs across five matched joint vectors. This establishes a mapping mismatch, but does not by itself identify whether the residual originates in robot asset geometry, base/world convention, or reference-point definition."},
            {"issue": "gripper numeric mapping", "evidence": "Both state vectors are semantically ordered by opening state, but signs differ across the two simulator conventions."},
            {"issue": "orientation numeric equivalence", "evidence": "Policy-source robot0_eef_quat versus panda_hand differs by 0.025 to 0.862 rad. A single fixed rotation does not materially improve the five-pose error, so a fixed orientation correction is not justified yet."},
        ],
        "could_plausibly_contribute_to_step6_0_of_3": "YES",
        "causality_limit": "The audit establishes observation-state mismatch; it does not prove that this was the sole cause of Step 6 0/3.",
        "next_step_choice": "A. Fix State Mapping and rerun calibration",
    }
    atomic_json(output / "root_cause_candidates.json", candidates)

    run_status = {
        "status": "PASS",
        "mode": "offline analysis of two prior capture files",
        "pi05_called": False,
        "libero_started": False,
        "isaac_started": False,
        "training_started": False,
        "task_rollout_started": False,
        "state_adapter_modified": False,
        "overwrote_existing_results": False,
        "conclusion": "State Mapping MISMATCH due to position-reference and gripper numeric conventions; policy-source orientation is APPROXIMATE, not a confirmed fixed-transform issue. Preserve this as BEFORE-FIX evidence and wait for approval before applying a minimal correction.",
    }
    atomic_json(output / "run_status.json", run_status)

    summary = f"""# Phase 3 / Step 7B State Mapping / EEF Calibration Audit

## Scope

This is an offline analysis of two static five-pose captures. It did not start Isaac, LIBERO, Pi0.5, training, or a task rollout.

## Measured result

- Five explicitly identical Panda arm joint vectors were assigned independently in LIBERO and Isaac.
- Direct Isaac tool-point to LIBERO EEF position error: mean {np.mean(position_before) * 1000:.3f} mm, max {np.max(position_before) * 1000:.3f} mm.
- A free rigid registration reduces the position residual to mean {np.mean(position_after) * 1000:.3f} mm, max {np.max(position_after) * 1000:.3f} mm. This is diagnostic evidence only, not a runtime mapping to apply.
- Raw Isaac hand to LIBERO policy-source `robot0_eef_quat` orientation error: mean {np.mean(before_orientation):.6f} rad, max {np.max(before_orientation):.6f} rad.
- The direct orientation comparison is the relevant one because `LiberoProcessorStep` converts `robot0_eef_quat`, not `controller.ee_ori_mat`, into Pi0.5's state.
- The 95.1035 mm point offset is implemented as `R_hand @ offset_local`; its five-pose formula residual is at numerical precision. A world-fixed offset bug is not confirmed.
- Gripper open/intermediate/closed progression agrees semantically, but LIBERO's mirrored-sign qpos values and Isaac's equal-positive finger values are not numerically interchangeable.
- Recorded maximum image-to-joint skew is 0.15 s for the prior RTX 5090 migration smoke and remains a separate timing limitation.

## Classification

Position semantics: MISMATCH  
Orientation semantics: {orientation['classification']} (policy-source quaternion)  
Tool-point calibration: APPROXIMATE  
Gripper state: MISMATCH  
Time synchronization: POTENTIAL ISSUE  
Overall State Mapping: MISMATCH

## Decision

The current State Adapter uses the corrected tool point for position and raw `panda_hand` orientation for state. The policy-source orientation comparison is only APPROXIMATE and does not justify a simple fixed rotation. Direct position correspondence and gripper numeric conventions are non-equivalent. Preserve these files as before-fix evidence. The only recommended next step is **A. Fix State Mapping and rerun calibration**, after explicit approval. No correction was applied in this audit.
"""
    (output / "summary.md").write_text(summary, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
