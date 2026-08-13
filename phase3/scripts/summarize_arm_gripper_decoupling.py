#!/usr/bin/env python3
"""Summarize the single Step 7C.5 diagnostic without changing formal statistics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path, default=None):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.result_dir
    trial = root / "diagnostic_trial"
    unit = load(root / "unit_tests.json", {})
    before = load(root / "before_fix_architecture.json", {})
    after = load(root / "after_fix_architecture.json", {})
    result = load(trial / "result.json", {})
    controller = load(trial / "controller.json", {})
    object_motion = load(trial / "object_motion.json", {})
    gripper = load(trial / "gripper.json", {})
    exception_text = (trial / "exception.txt").read_text(encoding="utf-8") if (trial / "exception.txt").is_file() else ""
    launch_text = (root / "diagnostic_launch.log").read_text(encoding="utf-8", errors="replace") if (root / "diagnostic_launch.log").is_file() else ""

    telemetry_names = ("descent_telemetry.json", "pink_telemetry.json", "gripper_telemetry.json", "safety_telemetry.json")
    telemetry = {}
    for name in telemetry_names:
        payload = load(trial / name, {"records": []})
        dump(root / name, payload)
        telemetry[name] = payload.get("records", [])

    descent = telemetry["descent_telemetry.json"]
    descent_steps = [row.get("control_step") for row in descent if isinstance(row.get("control_step"), int)]
    max_descent_step = max(descent_steps) if descent_steps else None
    passed_previous_region = max_descent_step is not None and max_descent_step >= 74
    full_descent = max_descent_step == 199 and bool(result.get("grasp_pose_reached"))
    pink_dimensions = sorted({
        (row.get("pink_configuration_nq"), row.get("pink_configuration_nv"))
        for row in descent
        if row.get("pink_configuration_nq") is not None
    })
    finger_failure_text = "\n".join((exception_text, launch_text)).lower()
    finger_limit_failure = "joint 8 violates configuration limits" in finger_failure_text or (
        "panda_finger_joint2" in finger_failure_text and "configuration limits" in finger_failure_text
    )
    close_executed = bool(result.get("close_executed")) or "command_close" in gripper
    lift_entered = bool(result.get("lift_entered"))
    lift_success = bool(result.get("success")) and result.get("failure_category") == "SUCCESS"
    max_object_motion = object_motion.get("max_vertical_displacement_m")
    object_motion_observed = max_object_motion is not None and float(max_object_motion) > 0.005
    exact_failure_step = None if result.get("success") else max_descent_step
    exit_code = int((root / "diagnostic_exit_code.txt").read_text().strip()) if (root / "diagnostic_exit_code.txt").is_file() else None
    architecture_validated = bool(
        unit.get("all_pass")
        and pink_dimensions == [(7, 7)]
        and not finger_limit_failure
        and passed_previous_region
    )

    trial_result = {
        **result,
        "trial_type": "DIAGNOSTIC / NOT COUNTED",
        "counted_in_formal_step7c": False,
        "formal_step7c_tomato_result_remains": "0/3",
        "pre_grasp_completed": bool(result.get("pre_grasp_completed")),
        "descent_entered": bool(descent_steps),
        "max_descent_control_step": max_descent_step,
        "passed_previous_failure_region_steps_73_74": passed_previous_region,
        "full_descent_completed": full_descent,
        "grasp_stage_reached": full_descent,
        "gripper_close_executed": close_executed,
        "object_contact_directly_measured": False,
        "object_motion_observed": object_motion_observed,
        "lift_entered": lift_entered,
        "lift_success": lift_success,
        "pink_configuration_dimensions_observed": [list(item) for item in pink_dimensions],
        "finger_limit_failure_reappeared": finger_limit_failure,
        "exact_failure_step": exact_failure_step,
        "exit_code": exit_code,
        "exception_present": bool(exception_text),
    }
    dump(root / "trial_result.json", trial_result)

    comparison = {
        "only_intended_architecture_change": "PINK 9D arm+finger configuration -> 7D arm-only configuration",
        "before": before,
        "after": after,
        "same_scene": True,
        "same_initial_state": 0,
        "same_object": "tomato_sauce",
        "same_pre_grasp_clearance_m": 0.085,
        "same_grasp_top_clearance_m": 0.010,
        "same_lift_delta_m": 0.060,
        "same_pink_costs": {"position": 5.0, "orientation": 0.25, "posture": 0.005},
        "same_controller_solver": "OSQP",
        "same_physics": True,
        "same_safety": True,
        "same_success_metric": True,
        "formal_results_modified": False,
        "diagnostic": {
            "passed_previous_failure_region": passed_previous_region,
            "finger_limit_failure_reappeared": finger_limit_failure,
            "full_descent_completed": full_descent,
            "lift_success": lift_success,
        },
    }
    dump(root / "before_after_comparison.json", comparison)

    if not unit.get("all_pass"):
        step_status = "FAIL"
    elif architecture_validated:
        step_status = "PASS"
    else:
        step_status = "PARTIAL"
    run_status = {
        "phase": "Phase 3 / Step 7C.5",
        "status": step_status,
        "single_diagnostic_trial_executed": True,
        "additional_trials_executed": False,
        "architecture_bug_fixed": architecture_validated,
        "tomato_formal_oracle_robustness_proven": False,
        "pi05_called": False,
        "predict_action_chunk_called": False,
        "training_run": False,
        "recommended_next_step": (
            "在获得新授权后，按固定协议进行新的 Tomato 3 次验证；不要回写历史 0/3。"
            if architecture_validated else
            "先分析本次唯一诊断的失败证据；未经授权不要实施第二个修复或重跑。"
        ),
    }
    dump(root / "run_status.json", run_status)

    summary = f"""# Phase 3 / Step 7C.5：手臂与夹爪 IK 解耦

## 结论

- 阶段状态：`{step_status}`
- 本次运行类型：`DIAGNOSTIC / NOT COUNTED`
- 正式 Step 7C Tomato 历史结果仍为：`0/3`
- PINK 配置维度：`{pink_dimensions or '未获得 runtime 证据'}`
- 通过原失败区间 step 73~74：`{'YES' if passed_previous_region else 'NO'}`
- 完整 descent：`{'YES' if full_descent else 'NO'}`
- 执行 gripper close：`{'YES' if close_executed else 'NO'}`
- 观察到物体运动（>5 mm）：`{'YES' if object_motion_observed else 'NO'}`
- 进入 lift：`{'YES' if lift_entered else 'NO'}`
- lift success：`{'YES' if lift_success else 'NO'}`
- 原 finger configuration-limit 错误再次出现：`{'YES' if finger_limit_failure else 'NO'}`

## 证据边界

这次只验证项目侧 7D arm-only PINK 与独立 gripper 路径。即使诊断成功，也不能修改历史正式统计，不能证明 Tomato Oracle 已具备固定协议下的稳健性，更不属于 Pi0.5、跨模拟器泛化或真实机器人结果。接触没有使用专门 contact sensor 直接测量；这里只单独报告物体运动证据。
"""
    (root / "summary.md").write_text(summary, encoding="utf-8")
    print(json.dumps({"status": step_status, "trial_result": trial_result, "run_status": run_status}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
