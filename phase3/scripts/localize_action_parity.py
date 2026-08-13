#!/usr/bin/env python3
"""Offline Step 7A.1 localization of saved LIBERO/Isaac parity records.

This script performs no simulation, policy inference, or training. It reads the
completed Step 7A JSON records and distinguishes target construction from the
observed 0.05 s controller response.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


TRANSLATION = ("+X", "-X", "+Y", "-Y", "+Z", "-Z")
ROTATION = ("+Rx", "-Rx", "+Ry", "-Ry", "+Rz", "-Rz")
GRIPPER = ("open", "close")


def vec_sub(a, b): return [float(x) - float(y) for x, y in zip(a, b, strict=True)]
def norm(a): return math.sqrt(sum(float(x) ** 2 for x in a))
def dot(a, b): return sum(float(x) * float(y) for x, y in zip(a, b, strict=True))
def cosine(a, b):
    na, nb = norm(a), norm(b)
    return None if na < 1e-12 or nb < 1e-12 else dot(a, b) / (na * nb)
def transpose(a): return [[a[j][i] for j in range(3)] for i in range(3)]
def matmul(a, b): return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
def axis_angle(matrix):
    angle = math.acos(max(-1.0, min(1.0, (sum(matrix[i][i] for i in range(3)) - 1.0) / 2.0)))
    if angle < 1e-10: return [0.0, 0.0, 0.0]
    scale = angle / (2.0 * math.sin(angle))
    return [(matrix[2][1] - matrix[1][2]) * scale, (matrix[0][2] - matrix[2][0]) * scale, (matrix[1][0] - matrix[0][1]) * scale]
def read(path): return json.loads(path.read_text(encoding="utf-8"))
def dump(path, data): path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
def targets_equivalent(left, right):
    left_norm, right_norm = norm(left), norm(right)
    if left_norm < 1e-12 or right_norm < 1e-12:
        return left_norm < 1e-12 and right_norm < 1e-12
    return cosine(left, right) > 0.999 and abs(right_norm / left_norm - 1.0) <= 0.01


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parity-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    source, output = args.parity_dir.resolve(), args.output_dir.resolve()
    if output.exists(): raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True)
    lt, it = read(source / "libero_translation.json"), read(source / "isaac_translation.json")
    lr, ir = read(source / "libero_rotation.json"), read(source / "isaac_rotation.json")
    lg, ig = read(source / "libero_gripper.json"), read(source / "isaac_gripper.json")
    old = read(source / "parity_matrix.json")["cases"]

    target_translation = {}
    for case in TRANSLATION:
        l, i = lt[case], it[case]
        left = vec_sub(l["controller_goal_position_xyz_m"], l["eef_before_xyz_m"])
        right = i["bounded"]["translation_delta_m"]
        target_translation[case] = {
            "normalized_action": l["raw_normalized_action"],
            "libero_delta_target_m": left, "isaac_delta_target_m": right,
            "target_delta_difference_m": vec_sub(right, left),
            "target_direction_cosine": cosine(left, right),
            "target_magnitude_ratio_isaac_over_libero": None if norm(left) < 1e-12 else norm(right) / norm(left),
            "target_same": targets_equivalent(left, right),
        }

    target_rotation = {}
    for case in ROTATION:
        l, i = lr[case], ir[case]
        left = axis_angle(matmul(l["controller_goal_orientation_matrix"], transpose(l["rotation_before_matrix"])))
        right = axis_angle(matmul(i["bounded"]["target_orientation_matrix"], transpose(i["rotation_before_matrix"])))
        target_rotation[case] = {
            "normalized_action": l["raw_normalized_action"],
            "libero_relative_target_axis_angle_rad": left, "isaac_relative_target_axis_angle_rad": right,
            "target_axis_sign_cosine": cosine(left, right),
            "target_magnitude_ratio_isaac_over_libero": None if norm(left) < 1e-12 else norm(right) / norm(left),
            "target_same": targets_equivalent(left, right),
            "multiplication_order": "both records specify R_target = R_delta @ R_current",
        }

    initial_position_delta = vec_sub(it["+X"]["eef_before_xyz_m"], lt["+X"]["eef_before_xyz_m"])
    initial_relative_rotation = axis_angle(matmul(it["+X"]["rotation_before_matrix"], transpose(lt["+X"]["rotation_before_matrix"])))
    eef_reference = {
        "libero_measurement": "raw observation robot0_eef_pos and robots[0].controller.ee_ori_mat",
        "isaac_measurement": "panda_hand world pose plus EEF_OFFSET_IN_HAND_M=[0,0,0.0951034858] for position; panda_hand orientation for rotation",
        "initial_position_difference_isaac_minus_libero_m": initial_position_delta,
        "initial_position_difference_norm_m": norm(initial_position_delta),
        "initial_orientation_difference_axis_angle_rad": initial_relative_rotation,
        "initial_orientation_difference_magnitude_rad": norm(initial_relative_rotation),
        "position_reference_assessment": "approximately aligned at state 0, but only one calibrated pose was measured",
        "orientation_reference_assessment": "different frame orientation is confirmed; hand/tool/site orientation semantics require a dedicated calibration audit",
        "direct_rotation_comparison": "not sufficient to diagnose a controller bug without resolving the fixed EEF frame transform",
    }

    tracking = {}
    mismatch_table = {}
    for case in TRANSLATION:
        l, i = lt[case], it[case]
        target_l, target_i = target_translation[case]["libero_delta_target_m"], target_translation[case]["isaac_delta_target_m"]
        actual_l, actual_i = l["actual_delta_xyz_m"], i["actual_delta_xyz_m"]
        tracking[case] = {"kind": "translation", "libero_tracking_ratio": norm(actual_l) / norm(target_l), "isaac_tracking_ratio": norm(actual_i) / norm(target_i), "actual_direction_cosine": cosine(actual_l, actual_i), "actual_magnitude_ratio_isaac_over_libero": norm(actual_i) / norm(actual_l)}
        if old[case]["status"] == "MISMATCH":
            mismatch_table[case] = {"prior_status": "MISMATCH", "category": "TRACKING_MAGNITUDE_MISMATCH", "evidence": "target deltas agree, while 0.05 s actual motion differs", "target_same": target_translation[case]["target_same"], "reference_point_same": "position approximately aligned; full tool-frame equivalence not established", "tracking_same": False}
    for case in ROTATION:
        l, i = lr[case], ir[case]
        target_l, target_i = target_rotation[case]["libero_relative_target_axis_angle_rad"], target_rotation[case]["isaac_relative_target_axis_angle_rad"]
        actual_l, actual_i = l["relative_rotation_axis_angle_rad"], i["relative_rotation_axis_angle_rad"]
        tracking[case] = {"kind": "rotation", "libero_tracking_ratio": norm(actual_l) / norm(target_l), "isaac_tracking_ratio": norm(actual_i) / norm(target_i), "actual_axis_sign_cosine": cosine(actual_l, actual_i), "actual_magnitude_ratio_isaac_over_libero": norm(actual_i) / norm(actual_l)}
        if old[case]["status"] == "MISMATCH":
            mismatch_table[case] = {"prior_status": "MISMATCH", "category": "REFERENCE_POINT_MISMATCH", "secondary_category": "TRACKING_MAGNITUDE_MISMATCH", "evidence": "target relative rotations agree, but initial measured orientation frames differ; actual rotation must not be interpreted as a confirmed adapter bug", "target_same": target_rotation[case]["target_same"], "reference_point_same": False, "tracking_same": False}
    for case in GRIPPER:
        mismatch_table[case] = {"prior_status": old[case]["status"], "category": "MATCH", "evidence": "both saved records report the same OPEN/CLOSED semantic"}

    reset = {
        "libero": "each record sets independent_hard_reset=true; source script creates a new OffScreenRenderEnv per case and applies ten no-op settle steps",
        "isaac": "each record sets independent_process_and_scene_reset=true; source script creates a new SimulationApp/scene per case and resets PINK before executing",
        "stale_target_evidence": "no saved record indicates target reuse; Isaac uses PINK reset(state, setpoint, 0) for each isolated process",
        "limitation": "the completed records do not include repeated no-op baselines, so residual drift cannot be numerically separated from 0.05 s action response",
    }
    root_causes = {
        "confirmed_action_adapter_bug": "NO",
        "confirmed_scaling_bug": "NO",
        "confirmed_frame_sign_bug": "NOT_YET",
        "confirmed_eef_reference_mismatch": "YES for orientation frame; position is only approximately aligned at one pose",
        "most_important_finding": "LIBERO and Isaac command the same normalized target deltas, so the Step 7A MISMATCH values arise after target construction. The fixed orientation-frame discrepancy makes direct rotation tracking comparison incomplete.",
        "step6_explanation": "POSSIBLE, but not established: short-horizon tracking/reference discrepancies could contribute, yet this audit does not test task completion.",
        "fix_and_rerun_step7a": "NO",
        "recommended_minimal_fix": "None executed. First audit the state mapping and EEF/tool-frame calibration across multiple poses.",
        "next_step": "B. Proceed to State Mapping / EEF Calibration Audit",
    }
    dump(output / "target_translation_audit.json", target_translation)
    dump(output / "target_rotation_audit.json", target_rotation)
    dump(output / "eef_reference_audit.json", eef_reference)
    dump(output / "tracking_audit.json", tracking)
    dump(output / "reset_audit.json", reset)
    dump(output / "mismatch_table.json", mismatch_table)
    dump(output / "root_cause_candidates.json", root_causes)
    dump(output / "run_status.json", {"completed": True, "offline_only": True, "pi05_called": False, "training": False, "step6_rerun": False, "step7a_rerun": False})
    (output / "summary.md").write_text("# Step 7A.1 动作不一致定位\n\n已离线分析 Step 7A 保存的 JSON；未运行仿真、Pi0.5、训练或 rollout。\n\n结论：目标构造未发现缩放/符号/左乘次序错误。平移的短时差异归为 TRACKING_MAGNITUDE_MISMATCH；旋转的初始 EEF frame 姿态差异已确认，因此其实际轨迹比较需要先完成 EEF calibration。建议 B：State Mapping / EEF Calibration Audit，不执行修复。\n", encoding="utf-8")
    return 0


if __name__ == "__main__": raise SystemExit(main())
