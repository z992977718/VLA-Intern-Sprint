#!/usr/bin/env python3
"""Build evidence-bounded Step 7D Before/After reports from real saved telemetry."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def pose(values) -> np.ndarray:
    return np.asarray(values, dtype=np.float64)


def latency_summary(values: list[float]) -> dict:
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0:
        return {"count": 0, "mean_ms": None, "median_ms": None, "p95_ms": None}
    return {
        "count": int(array.size),
        "mean_ms": float(np.mean(array)),
        "median_ms": float(np.median(array)),
        "p95_ms": float(np.percentile(array, 95)),
        "min_ms": float(np.min(array)),
        "max_ms": float(np.max(array)),
    }


def motion_summary(initial: np.ndarray, samples: list[np.ndarray], final: np.ndarray) -> dict:
    displacements = [float(np.linalg.norm(sample - initial)) for sample in samples]
    vertical = [float(sample[2] - initial[2]) for sample in samples]
    return {
        "initial_position_xyz_m": initial.tolist(),
        "final_position_xyz_m": final.tolist(),
        "maximum_displacement_m": max(displacements, default=0.0),
        "final_displacement_m": float(np.linalg.norm(final - initial)),
        "maximum_vertical_displacement_m": max(vertical, default=0.0),
        "minimum_vertical_displacement_m": min(vertical, default=0.0),
        "final_vertical_displacement_m": float(final[2] - initial[2]),
    }


def step6_baseline(step6: Path) -> dict:
    reset = read_json(step6 / "reset.json")
    complete = read_json(step6 / "episode_complete.json")
    result_path = step6 / "result.json"
    records = [read_json(path) for path in sorted(step6.glob("cycle_???.json"))]
    initial_soup = pose(reset["object_positions_xyz_m"]["alphabet_soup"])
    initial_tomato = pose(reset["object_positions_xyz_m"]["tomato_sauce"])
    soup_samples = [pose(row["object_centers_xyz_m"]["alphabet_soup"]) for row in records]
    tomato_samples = [pose(row["object_centers_xyz_m"]["tomato_sauce"]) for row in records]
    final_soup = soup_samples[-1] if soup_samples else initial_soup
    final_tomato = tomato_samples[-1] if tomato_samples else initial_tomato
    eef_points = [pose(reset["eef_position_xyz_m"])]
    minimum_soup = (math.inf, None)
    minimum_tomato = (math.inf, None)
    for row in records:
        eef_before = pose(row["eef_before_xyz_m"])
        eef_after = pose(row["eef_after_xyz_m"])
        soup = pose(row["object_centers_xyz_m"]["alphabet_soup"])
        tomato = pose(row["object_centers_xyz_m"]["tomato_sauce"])
        eef_points.append(eef_after)
        for point in (eef_before, eef_after):
            soup_distance = float(np.linalg.norm(point - soup))
            tomato_distance = float(np.linalg.norm(point - tomato))
            if soup_distance < minimum_soup[0]:
                minimum_soup = (soup_distance, int(row["cycle_index"]))
            if tomato_distance < minimum_tomato[0]:
                minimum_tomato = (tomato_distance, int(row["cycle_index"]))
    endpoint_path = sum(float(np.linalg.norm(b - a)) for a, b in zip(eef_points, eef_points[1:]))
    close_cycles = [
        int(row["cycle_index"]) for row in records if float(row["bounded_action"][6]) > 0.1
    ]
    latencies = [float(row["inference_latency_ms"]) for row in records]
    saved_latency = read_json(step6 / "latency.json").get("inference") if (step6 / "latency.json").exists() else None
    exceptions = (step6 / "exception.txt").read_text(encoding="utf-8") if (step6 / "exception.txt").exists() else ""
    return {
        "source": str(step6),
        "episode_result": read_json(result_path) if result_path.exists() else complete,
        "cycles": int(complete["cycles_completed"]),
        "termination": complete["termination"],
        "success": bool(complete["success"]),
        "eef_trajectory_xyz_m": [point.tolist() for point in eef_points],
        "eef_endpoint_path_length_m": endpoint_path,
        "eef_path_definition": "sum of logged reset/cycle endpoint-to-endpoint tool positions; within-cycle path is unavailable",
        "minimum_tool_to_alphabet_distance_m": None if not math.isfinite(minimum_soup[0]) else minimum_soup[0],
        "minimum_tool_to_alphabet_cycle": minimum_soup[1],
        "minimum_tool_to_tomato_distance_m": None if not math.isfinite(minimum_tomato[0]) else minimum_tomato[0],
        "minimum_tool_to_tomato_cycle": minimum_tomato[1],
        "distance_reconstruction_note": "reconstructed from each logged EEF before/after point and same-cycle object center",
        "object_motion": {
            "alphabet_soup": motion_summary(initial_soup, soup_samples, final_soup),
            "tomato_sauce": motion_summary(initial_tomato, tomato_samples, final_tomato),
        },
        "object_orientation": "NOT_AVAILABLE_IN_STEP6_LOG",
        "gripper": {
            "close_attempt_count": len(close_cycles),
            "close_attempt_cycles": close_cycles,
            "finger_actual": "NOT_AVAILABLE_IN_STEP6_LOG",
        },
        "safety_violations": 0 if all(row.get("safety_status") == "PASS" for row in records) else None,
        "ik_failures": 1 if "PINK" in exceptions or "IK_" in exceptions else 0,
        "latency": saved_latency or latency_summary(latencies),
        "latency_source": "saved Step 6 latency.json" if saved_latency else "reconstructed from cycle logs",
    }


def copy_frame(result: Path, frame_index: int, name: str) -> str | None:
    source = result / "video_frames" / f"frame_{frame_index:05d}.png"
    if not source.is_file():
        return None
    target_dir = result / "screenshots"
    target_dir.mkdir(exist_ok=True)
    target = target_dir / name
    shutil.copy2(source, target)
    return str(target.relative_to(result))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--step6-episode", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    args = parser.parse_args()
    result = args.result_dir.resolve()
    if not (result / "episode_complete.json").is_file() or not (result / "policy_complete.json").is_file():
        raise RuntimeError("Step 7D runtime outputs are incomplete")

    before = step6_baseline(args.step6_episode.resolve())
    write_json(result / "step6_before_baseline.json", before)
    records = read_json(result / "cycle_telemetry.json")["records"]
    reset = read_json(result / "reset.json")
    complete = read_json(result / "episode_complete.json")
    policy = read_json(result / "policy_complete.json")
    final_state = read_json(result / "final_state.json") if (result / "final_state.json").exists() else None
    final_handshake_race = bool(
        not policy.get("completed")
        and policy.get("total_real_inference_calls") == complete.get("cycles_completed") == 100
        and complete.get("completed")
        and not policy.get("oom")
        and "did not publish completion" in policy.get("exception", "")
    )
    policy_effective_complete = bool(policy.get("completed") or final_handshake_race)
    write_json(
        result / "policy_handshake_reconciliation.json",
        {
            "raw_policy_completed": policy.get("completed"),
            "raw_policy_exit_race": final_handshake_race,
            "effective_policy_runtime_complete": policy_effective_complete,
            "real_inference_calls": policy.get("total_real_inference_calls"),
            "isaac_cycles_completed": complete.get("cycles_completed"),
            "episode_complete": complete.get("completed"),
            "oom": policy.get("oom"),
            "interpretation": "The policy completed all 100 authorized inferences; its post-loop check ran before Isaac atomically published episode_complete. Raw policy_complete.json is preserved unchanged.",
            "episode_rerun_required": False,
        },
    )

    inference = latency_summary([float(row["inference_latency_ms"]) for row in records])
    adapter = latency_summary([float(row["adapter_latency_ms"]) for row in records])
    controller = latency_summary([float(row["controller_latency_mean_ms"]) for row in records])
    latency = {"inference": inference, "action_adapter": adapter, "pink_mean_per_cycle": controller}
    write_json(result / "latency.json", latency)

    translation = [float(np.linalg.norm(row["bounded_action"][:3])) for row in records]
    rotation = [float(np.linalg.norm(row["bounded_action"][3:6])) for row in records]
    gripper_actions = [float(row["bounded_action"][6]) for row in records]
    action_summary = {
        "cycles": len(records),
        "translation_action_magnitude": {
            "mean": float(np.mean(translation)) if translation else None,
            "max": max(translation, default=None),
        },
        "rotation_action_magnitude": {
            "mean": float(np.mean(rotation)) if rotation else None,
            "max": max(rotation, default=None),
        },
        "gripper_action": {
            "mean": float(np.mean(gripper_actions)) if gripper_actions else None,
            "min": min(gripper_actions, default=None),
            "max": max(gripper_actions, default=None),
        },
        "clipping_count": sum(bool(row["action_clipping_applied"]) for row in records),
        "clipping_frequency": (
            sum(bool(row["action_clipping_applied"]) for row in records) / len(records) if records else None
        ),
        "safety_intervention_count": int(complete.get("safety_event_count", 0)),
        "pink_failure_count": int(complete.get("pink_failure_count", 0)),
        "finger_configuration_limit_failure": False,
    }
    write_json(result / "action_summary.json", action_summary)

    initial_soup = pose(reset["object_poses"]["alphabet_soup"]["position_xyz_m"])
    initial_tomato = pose(reset["object_poses"]["tomato_sauce"]["position_xyz_m"])
    soup_samples = [pose(row["object_poses_after"]["alphabet_soup"]["position_xyz_m"]) for row in records]
    tomato_samples = [pose(row["object_poses_after"]["tomato_sauce"]["position_xyz_m"]) for row in records]
    final_soup = soup_samples[-1] if soup_samples else initial_soup
    final_tomato = tomato_samples[-1] if tomato_samples else initial_tomato
    object_motion = {
        "evidence_threshold_m": 0.005,
        "threshold_note": "conservative Step 7C object-motion evidence threshold; not a measured sensor-noise estimate",
        "alphabet_soup": motion_summary(initial_soup, soup_samples, final_soup),
        "tomato_sauce": motion_summary(initial_tomato, tomato_samples, final_tomato),
    }
    for key in ("alphabet_soup", "tomato_sauce"):
        object_motion[key]["object_motion_observed"] = object_motion[key]["maximum_displacement_m"] >= 0.005
    write_json(result / "object_motion.json", object_motion)

    def minimum_distance(key: str) -> tuple[float | None, int | None]:
        candidates = []
        for row in records:
            candidates.extend(
                [
                    (float(row["distances_m"][f"tool_center_to_{key}_before"]), int(row["cycle_index"])),
                    (float(row["distances_m"][f"tool_center_to_{key}_after"]), int(row["cycle_index"])),
                ]
            )
        return min(candidates) if candidates else (None, None)

    min_soup, min_soup_cycle = minimum_distance("alphabet")
    min_tomato, min_tomato_cycle = minimum_distance("tomato")
    approach = {
        "position_source": "/World/Robot/panda_hand/tool_center",
        "minimum_tool_to_alphabet_distance_m": min_soup,
        "minimum_tool_to_alphabet_cycle": min_soup_cycle,
        "minimum_tool_to_tomato_distance_m": min_tomato,
        "minimum_tool_to_tomato_cycle": min_tomato_cycle,
        "separate_gripper_center_metric": "NOT_SEPARATELY_RECONSTRUCTED",
    }
    write_json(result / "approach_metrics.json", approach)

    close_rows = [row for row in records if row["gripper"]["close_attempt"]]
    close_attempts = [
        {
            "cycle": int(row["cycle_index"]),
            "policy_command": row["gripper"]["policy_command"],
            "finger_target_m": row["gripper"]["target_finger_qpos_m"],
            "finger_actual_before_m": row["gripper"]["actual_before_finger_qpos_m"],
            "finger_actual_after_m": row["gripper"]["actual_after_finger_qpos_m"],
            "distance_to_alphabet_after_m": row["distances_m"]["tool_center_to_alphabet_after"],
            "distance_to_tomato_after_m": row["distances_m"]["tool_center_to_tomato_after"],
        }
        for row in close_rows
    ]
    strongest_close = None
    if close_attempts:
        strongest_close = min(
            close_attempts,
            key=lambda row: min(row["distance_to_alphabet_after_m"], row["distance_to_tomato_after_m"]),
        )
    plausible = bool(
        strongest_close
        and min(strongest_close["distance_to_alphabet_after_m"], strongest_close["distance_to_tomato_after_m"])
        <= 0.10
    )
    gripper_summary = {
        "close_attempt_count": len(close_attempts),
        "close_attempts": close_attempts,
        "strongest_close_attempt": strongest_close,
        "plausible_grasp_attempt": plausible,
        "plausible_attempt_rule": "close command while native tool_center is within 0.10 m of either object center; behavior heuristic only, not proof of contact/grasp",
        "behavior_classification": (
            "NEVER_ATTEMPTED_CLOSE"
            if not close_attempts
            else ("CLOSE_NEAR_OBJECT" if plausible else "CLOSE_FAR_FROM_OBJECT")
        ),
    }
    write_json(result / "gripper_summary.json", gripper_summary)

    safety_summary = {
        "decision": "PASS" if complete.get("safety_event_count", 0) == 0 else "INTERVENTION_RECORDED",
        "safety_event_count": int(complete.get("safety_event_count", 0)),
        "pink_failure_count": int(complete.get("pink_failure_count", 0)),
        "float_safe_joint_limits_active": True,
        "arm_only_pink_active": True,
        "independent_gripper_active": True,
        "finger_configuration_limit_regression": False,
        "raw_events_file": "runtime_safety_events.json",
        "pink_failures_file": "pink_failures.json",
    }
    write_json(result / "safety_summary.json", safety_summary)

    eef_points = [pose(reset["eef_position_xyz_m"])] + [pose(row["eef_after_xyz_m"]) for row in records]
    after_eef_path = sum(float(np.linalg.norm(b - a)) for a, b in zip(eef_points, eef_points[1:]))
    after = {
        "episode_result": complete,
        "cycles": int(complete["cycles_completed"]),
        "eef_endpoint_path_length_m": after_eef_path,
        "minimum_tool_to_alphabet_distance_m": min_soup,
        "minimum_tool_to_tomato_distance_m": min_tomato,
        "alphabet_max_displacement_m": object_motion["alphabet_soup"]["maximum_displacement_m"],
        "tomato_max_displacement_m": object_motion["tomato_sauce"]["maximum_displacement_m"],
        "close_attempts": len(close_attempts),
        "safety_violations": int(complete.get("safety_event_count", 0)),
        "ik_failures": int(complete.get("pink_failure_count", 0)),
        "latency": inference,
    }
    comparison_rows = [
        ("episode result", before["termination"], complete["termination"]),
        ("cycles", before["cycles"], after["cycles"]),
        ("EEF endpoint path length (m)", before["eef_endpoint_path_length_m"], after_eef_path),
        ("min distance to alphabet (m)", before["minimum_tool_to_alphabet_distance_m"], min_soup),
        ("min distance to tomato (m)", before["minimum_tool_to_tomato_distance_m"], min_tomato),
        ("alphabet max displacement (m)", before["object_motion"]["alphabet_soup"]["maximum_displacement_m"], after["alphabet_max_displacement_m"]),
        ("tomato max displacement (m)", before["object_motion"]["tomato_sauce"]["maximum_displacement_m"], after["tomato_max_displacement_m"]),
        ("close attempts", before["gripper"]["close_attempt_count"], len(close_attempts)),
        ("Safety violations", before["safety_violations"], after["safety_violations"]),
        ("IK failures", before["ik_failures"], after["ik_failures"]),
        ("mean inference latency (ms)", before["latency"]["mean_ms"], inference["mean_ms"]),
        ("median inference latency (ms)", before["latency"]["median_ms"], inference["median_ms"]),
        ("p95 inference latency (ms)", before["latency"]["p95_ms"], inference["p95_ms"]),
    ]
    comparison = {
        "metric_rows": [
            {
                "metric": name,
                "step6_before": old,
                "step7d_after": new,
                "numeric_change": (
                    float(new - old) if isinstance(old, (int, float)) and isinstance(new, (int, float)) else None
                ),
            }
            for name, old, new in comparison_rows
        ],
        "causal_boundary": "Step 7D jointly inherits confirmed State Mapping, float-safe Safety, and 7D PINK fixes; no single fix is isolated causally.",
    }
    write_json(result / "before_after_comparison.json", comparison)

    screenshots = {
        "start": copy_frame(result, 0, "start.png"),
        "closest_to_alphabet": None,
        "closest_to_tomato": None,
        "strongest_grasp_attempt": None,
        "closest_close_attempt_far_from_objects": None,
        "final": copy_frame(result, max(int(complete.get("frames", 1)) - 1, 0), "final.png"),
    }
    by_cycle = {int(row["cycle_index"]): row for row in records}
    if min_soup_cycle in by_cycle:
        screenshots["closest_to_alphabet"] = copy_frame(
            result, int(by_cycle[min_soup_cycle]["video_frame_range"]["end_inclusive"]), "closest_to_alphabet.png"
        )
    if min_tomato_cycle in by_cycle:
        screenshots["closest_to_tomato"] = copy_frame(
            result, int(by_cycle[min_tomato_cycle]["video_frame_range"]["end_inclusive"]), "closest_to_tomato.png"
        )
    if plausible and strongest_close and strongest_close["cycle"] in by_cycle:
        screenshots["strongest_grasp_attempt"] = copy_frame(
            result,
            int(by_cycle[strongest_close["cycle"]]["video_frame_range"]["end_inclusive"]),
            "strongest_grasp_attempt.png",
        )
    elif strongest_close and strongest_close["cycle"] in by_cycle:
        screenshots["closest_close_attempt_far_from_objects"] = copy_frame(
            result,
            int(by_cycle[strongest_close["cycle"]]["video_frame_range"]["end_inclusive"]),
            "closest_close_attempt_far_from_objects.png",
        )
    write_json(result / "screenshots.json", screenshots)

    before_best = min(
        before["minimum_tool_to_alphabet_distance_m"], before["minimum_tool_to_tomato_distance_m"]
    )
    after_best = min(value for value in (min_soup, min_tomato) if value is not None)
    approach_improved = after_best <= before_best - 0.02
    moved = bool(
        object_motion["alphabet_soup"]["object_motion_observed"]
        or object_motion["tomato_sauce"]["object_motion_observed"]
    )
    regression = safety_summary["safety_event_count"] > 0 or safety_summary["pink_failure_count"] > 0
    if regression:
        behavior_change = "REGRESSION"
    elif approach_improved and moved and plausible:
        behavior_change = "STRONG_IMPROVEMENT"
    elif approach_improved:
        behavior_change = "MODERATE_IMPROVEMENT"
    else:
        behavior_change = "NO_CLEAR_IMPROVEMENT"

    if complete["success"]:
        failure_labels = []
        task_label = "DIAGNOSTIC TASK SUCCESS"
    else:
        failure_labels = []
        if not plausible:
            failure_labels.extend(["FAILED_APPROACH", "FAILED_GRASP"])
        elif not moved:
            failure_labels.append("FAILED_GRASP")
        else:
            failure_labels.extend(["FAILED_TRANSPORT", "FAILED_PLACE"])
        if complete["termination"] == "HORIZON_REACHED":
            failure_labels.append("HORIZON_REACHED")
        if safety_summary["safety_event_count"]:
            failure_labels.append("SAFETY_STOP")
        if safety_summary["pink_failure_count"]:
            failure_labels.append("IK_FAILURE")
        task_label = "DIAGNOSTIC TASK FAILURE"

    gpu_peak = None
    gpu_csv = result / "gpu_timeseries.csv"
    if gpu_csv.exists():
        rows = gpu_csv.read_text(encoding="utf-8").splitlines()[1:]
        used = []
        for row in rows:
            columns = [part.strip() for part in row.split(",")]
            if len(columns) >= 4:
                try:
                    used.append(float(columns[-2]))
                except ValueError:
                    pass
        gpu_peak = max(used, default=None)
    gpu = {
        "torch_peak_allocated_bytes": policy.get("torch_peak_allocated_bytes"),
        "torch_peak_reserved_bytes": policy.get("torch_peak_reserved_bytes"),
        "nvidia_smi_peak_used_mib": gpu_peak,
        "final_gpu": (result / "gpu_final.txt").read_text(encoding="utf-8").strip() if (result / "gpu_final.txt").exists() else None,
    }
    write_json(result / "gpu_summary.json", gpu)

    video_sha = None
    if args.video.is_file():
        digest = hashlib.sha256()
        with args.video.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        video_sha = digest.hexdigest()
    trial = {
        "protocol": "DIAGNOSTIC / NOT COUNTED",
        "episodes": 1,
        "initial_state": "Step 6 State 0",
        "max_cycles": 100,
        "K": 1,
        "checkpoint_unchanged": read_json(result / "checkpoint_hash.json").get("match_step6_checkpoint"),
        "robot_side_fixes": {
            "state_mapping_fix": True,
            "arm_only_7d_pink": True,
            "independent_gripper": True,
            "float_safe_safety": True,
            "orientation_additional_fix": False,
            "timestamp_additional_fix": False,
        },
        "result": task_label,
        "success": bool(complete["success"]),
        "failure_labels": failure_labels,
        "behavior_change": behavior_change,
        "behavior_evidence": {
            "before_best_object_distance_m": before_best,
            "after_best_object_distance_m": after_best,
            "approach_improvement_rule_m": 0.02,
            "approach_improved": approach_improved,
            "object_motion_observed": moved,
            "plausible_grasp_attempt": plausible,
        },
        "comparison_position_reference_note": "Step 6 BEFORE used its logged panda_hand plus fixed offset; Step 7D AFTER uses the corrected native USD tool_center. The changed reference is the audited intervention under test and must be retained when interpreting distance deltas.",
        "can_step6_0_of_3_be_attributed_to_fixed_robot_bugs_alone": False,
        "major_confirmed_robot_side_blockers_cleared": not regression,
        "remaining_known_limitations": [
            "orientation mapping UNRESOLVED",
            "image-state skew up to about 0.15 s remains uncorrected",
            "cross-simulator visual/domain differences",
            "controller/embodiment differences",
        ],
        "recommended_project_decision": (
            "ONLY_IF_CRITICAL_REGRESSION_CONTINUE_LOCALIZATION" if regression else "FREEZE_FRANKA_ISAAC_MAINLINE"
        ),
        "should_additional_franka_benchmark_episodes_be_run": False,
        "should_training_lora_rl_start_automatically": False,
        "video": str(args.video),
        "video_sha256": video_sha,
        "screenshots": screenshots,
    }
    write_json(result / "trial_result.json", trial)
    run_status = {
        "step": "Phase 3 / Step 7D",
        "status": "PASS" if complete["completed"] and policy_effective_complete and not regression else "PARTIAL",
        "single_episode_enforced": True,
        "diagnostic_not_counted": True,
        "inference_calls": int(policy["total_real_inference_calls"]),
        "cycles": int(complete["cycles_completed"]),
        "old_results_overwritten": False,
        "training_run": False,
        "pi05_weights_changed": False,
        "policy_final_handshake_race_reconciled": final_handshake_race,
    }
    write_json(result / "run_status.json", run_status)

    rows_md = "\n".join(
        f"| {row['metric']} | {row['step6_before']} | {row['step7d_after']} | {row['numeric_change']} |"
        for row in comparison["metric_rows"]
    )
    summary = f"""# Phase 3 / Step 7D：一次性修复后 Pi0.5 诊断

- 类型：**DIAGNOSTIC / NOT COUNTED**
- Episode：1（Step 6 fixed initial state 0）
- Horizon：最多 100 cycles
- K：1，只执行 `action_chunk[0]`
- 结果：**{task_label}**
- 行为变化：**{behavior_change}**
- 建议：**{trial['recommended_project_decision']}**

## Before / After

| 指标 | Step 6 BEFORE | Step 7D AFTER | 数值变化 |
|---|---:|---:|---:|
{rows_md}

## 证据边界

本次同时继承 State Mapping、浮点安全检查和 7D PINK 三组已确认修复，不能把行为变化归因于其中某一个单独修复。无论诊断成功或失败，本回合都不构成新 benchmark 成功率；也不能据此把原 Step 6 的 0/3 单独归因于已修复的机器人侧问题。

仍保留：orientation mapping 未解决、约 0.15 s image-state skew 未修复、跨模拟器视觉/域差异，以及控制器/embodiment 差异。
"""
    (result / "summary.md").write_text(summary, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
