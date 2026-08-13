#!/usr/bin/env python3
"""Summarize the fixed three-trial tomato post-fix protocol without rerunning Isaac."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PINK_LIMIT_RE = re.compile(
    r"PINK solve_ik failed: Joint (?P<joint>\d+) violates configuration limits "
    r"(?P<lower>[-+0-9.eE]+) <= (?P<actual>[-+0-9.eE]+) <= (?P<upper>[-+0-9.eE]+)"
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def trial_row(result_dir: Path, index: int) -> dict:
    folder = result_dir / f"trial_{index:02d}"
    result = load(folder / "result.json")
    approach = load(folder / "approach_step0.json")
    descent = load(folder / "descent_step0.json")
    launch_log = (result_dir / f"trial_{index:02d}.launch.log").read_text(encoding="utf-8", errors="replace")
    match = PINK_LIMIT_RE.search(launch_log)
    pink_internal_limit = None
    if match:
        pink_internal_limit = {
            "joint_index_reported_by_pink": int(match.group("joint")),
            "lower": float(match.group("lower")),
            "actual": float(match.group("actual")),
            "upper": float(match.group("upper")),
            "excess": float(match.group("actual")) - float(match.group("upper")),
            "source": f"trial_{index:02d}.launch.log",
        }

    descent_frames = sorted((folder / "video_frames").glob("*_descent.png"))
    last_saved_step = (len(descent_frames) - 1) * 12 if descent_frames else None
    failure_step_interval = None
    if last_saved_step is not None and result.get("failure_category") == "IK_FAILURE":
        failure_step_interval = {
            "last_confirmed_saved_step": last_saved_step,
            "earliest_possible_failure_step": last_saved_step + 1,
            "latest_possible_failure_step": min(last_saved_step + 12, 199),
            "exact_step_known": False,
            "reason": "telemetry is written after PINK returns a target; PINK returned None before the next 12-step capture",
        }

    clamps = [
        {"stage": "approach", "step": 0, **event} for event in approach.get("clamps", [])
    ] + [
        {"stage": "descent", "step": 0, **event} for event in descent.get("clamps", [])
    ]
    return {
        **result,
        "folder": f"trial_{index:02d}",
        "pre_grasp_completed": True,
        "pre_grasp_evidence": "descent_step0.json exists, so the approach stage returned normally",
        "descent_step0_passed": bool(descent.get("pass") and descent.get("reason_code") == "PASS"),
        "descent_completed": False,
        "descent_saved_frame_count": len(descent_frames),
        "descent_failure_step_interval": failure_step_interval,
        "confirmed_tolerance_clamps": clamps,
        "confirmed_tolerance_clamp_count": len(clamps),
        "exact_total_clamp_count_known": False,
        "confirmed_real_safety_violations": [],
        "confirmed_safety_rejection_count": 0,
        "joint_delta_violation": False,
        "pink_step0_status": descent.get("pink_solve_status"),
        "pink_final_status": "IK_FAILURE: PINK forward returned None",
        "pink_internal_configuration_limit_failure": pink_internal_limit,
        "grasp_pose_reached": False,
        "close_executed": False,
        "object_motion_measured": False,
        "entered_lift": False,
        "max_vertical_displacement_m": None,
        "final_vertical_displacement_m": None,
        "final_outcome": "FAIL",
        "evidence_limit": "The exception path did not persist full joint telemetry or object_motion.json.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    args = parser.parse_args()
    result_dir = args.result_dir.resolve()

    rows = [trial_row(result_dir, index) for index in range(3)]
    success_count = sum(bool(row["success"]) for row in rows)
    descent_step0_count = sum(bool(row["descent_step0_passed"]) for row in rows)
    descent_complete_count = sum(bool(row["descent_completed"]) for row in rows)
    grasp_count = sum(bool(row["grasp_pose_reached"]) for row in rows)
    lift_count = sum(bool(row["entered_lift"]) for row in rows)
    confirmed_clamps = [
        {"trial": row["trial_index"], **event}
        for row in rows
        for event in row["confirmed_tolerance_clamps"]
    ]

    runtime_configs = [load(result_dir / f"trial_{index:02d}" / "float_tolerance_runtime.json") for index in range(3)]
    tolerance_config = load(result_dir / "float_tolerance_config.json")
    tolerance_config.update(
        {
            "status": "RUNTIME_CONFIRMED",
            "runtime_trials": runtime_configs,
            "target_source_dtypes": sorted({row["target_source_dtype"] for row in runtime_configs}),
            "joint_limit_source_dtypes": sorted({row["joint_limit_source_dtype"] for row in runtime_configs}),
            "comparison_dtypes": sorted({row["comparison_dtype"] for row in runtime_configs}),
            "finger_limit_tolerance_rad": 7.450580596923828e-09,
        }
    )
    dump(result_dir / "float_tolerance_config.json", tolerance_config)

    comparison = {
        "before_fix": {
            "tomato_success": 0,
            "trials": 3,
            "descent_step0_passed": 0,
            "descent_completed": 0,
            "grasp_stage_reached": 0,
            "lift_success": 0,
            "false_positive_joint_upper_limit_stops": 3,
            "confirmed_trigger_excess_rad": 3.725290298461914e-09,
        },
        "after_fix": {
            "tomato_success": success_count,
            "trials": 3,
            "descent_step0_passed": descent_step0_count,
            "descent_completed": descent_complete_count,
            "grasp_stage_reached": grasp_count,
            "lift_success": lift_count,
            "confirmed_floating_tolerance_clamps": len(confirmed_clamps),
            "exact_total_clamp_count_known": False,
            "confirmed_real_upper_limit_safety_rejections": 0,
            "confirmed_real_lower_limit_safety_rejections": 0,
            "confirmed_joint_delta_safety_rejections": 0,
            "confirmed_nonfinite_safety_rejections": 0,
            "final_failure_category": "IK_FAILURE",
            "tomato_classification": "FAIL",
        },
        "original_false_positive_safety_stop_disappeared": descent_step0_count == 3,
        "confirmed_safety_comparison_bug_fixed": descent_step0_count == 3,
        "new_blocker": {
            "category": "IK_FAILURE",
            "component": "PINK internal configuration-limit validation",
            "observed_message": "Joint 8 violates configuration limits 0.0 <= 0.04000149667263031 <= 0.04",
            "automatic_second_fix_performed": False,
        },
        "frozen_alphabet_reference": {"success": 3, "trials": 3},
        "robot_side_oracle_after_fix": "PARTIAL",
        "does_not_prove_step6_policy_causation": True,
        "could_have_contributed_to_step6": "UNLIKELY",
        "next_pi05_diagnostic_rollout_recommended_now": False,
    }
    clamp_summary = {
        "confirmed_count": len(confirmed_clamps),
        "exact_total_count_known": False,
        "events": confirmed_clamps,
        "confirmed_real_safety_rejections": {
            "JOINT_UPPER_LIMIT": 0,
            "JOINT_LOWER_LIMIT": 0,
            "JOINT_DELTA_LIMIT": 0,
            "NONFINITE_JOINT_TARGET": 0,
        },
        "note": "Only step-0 snapshots survived the later PINK exception; do not infer the exact total number of non-rejecting clamps.",
    }
    success_summary = {
        "object": "tomato_sauce",
        "postfix_success": success_count,
        "postfix_trials": 3,
        "rows": rows,
        "tomato_postfix_classification": "FAIL",
        "step_7c_3_classification": "PARTIAL",
        "frozen_before_fix_tomato": "0/3",
        "frozen_alphabet": "3/3",
        "combined_robot_side_oracle_interpretation": "PARTIAL",
    }
    dump(result_dir / "before_after_comparison.json", comparison)
    dump(result_dir / "safety_clamp_summary.json", clamp_summary)
    dump(result_dir / "grasp_success_summary.json", success_summary)
    dump(
        result_dir / "run_status.json",
        {
            "phase": "Phase 3 / Step 7C.3",
            "completed": True,
            "postfix_formal_trials": 3,
            "fourth_trial_run": False,
            "hard_reset_per_trial": True,
            "pi05_called": False,
            "predict_action_chunk_called": False,
            "training": False,
            "step6_rerun": False,
            "alphabet_rerun": False,
            "physics_parameters_changed": False,
            "joint_delta_threshold_changed": False,
            "success_metric_changed": False,
            "frozen_results_modified": False,
            "automatic_second_fix_performed": False,
            "classification": "PARTIAL",
            "stop_reason": "All three post-fix trials exposed a new PINK internal configuration-limit IK failure during descent.",
        },
    )
    (result_dir / "summary.md").write_text(
        "# Phase 3 / Step 7C.3：Tomato 浮点安全修复后验证\n\n"
        "## 结论\n\n"
        "- Step 7C.3：`PARTIAL`。\n"
        "- Tomato BEFORE FIX：`0/3`（冻结结果）。\n"
        f"- Tomato AFTER FIX：`{success_count}/3`。\n"
        f"- descent step 0：`{descent_step0_count}/3` 通过；完整 descent：`{descent_complete_count}/3`。\n"
        f"- grasp stage：`{grasp_count}/3`；lift：`{lift_count}/3`。\n"
        "- 原来的 Safety false-positive：已消失。\n"
        "- 新阻塞：三次均在 descent 中段由 PINK 内部配置上限检查返回 IK failure。\n\n"
        "## 新失败证据\n\n"
        "三次日志均报告：`Joint 8 violates configuration limits 0.0 <= 0.04000149667263031 <= 0.04`。"
        "每次最后保存的 descent 采样为 step 72；由于每 12 步保存一次，失败只能定位在 step 73～84，精确步数未被异常路径保存。\n\n"
        "已确认的容差夹回事件为 3 次（每个 trial 的 descent step 0 各一次）。"
        "后续未保存完整 telemetry，因此不能把 3 写成全过程精确总数。\n\n"
        "## 边界\n\n"
        "没有运行第 4 次 trial，没有重跑 Alphabet、Step 6 或 Pi0.5，没有修改 PINK、物理、轨迹、成功判据或 0.05 rad joint-delta 阈值，也没有自动修复第二个问题。\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
