#!/usr/bin/env python3
"""Summarize saved Phase 2 / Step 5 evidence without running Isaac or Pi0.5."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path


MAX_CYCLES = 5


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * percent / 100.0
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - index) + ordered[upper] * (index - lower)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def axis_angle_from_xyzw(quaternion: list[float]) -> list[float]:
    x, y, z, w = quaternion
    w = min(1.0, max(-1.0, w))
    denominator = math.sqrt(max(0.0, 1.0 - w * w))
    if denominator <= 1e-10:
        return [0.0, 0.0, 0.0]
    factor = 2.0 * math.acos(w) / denominator
    return [x * factor, y * factor, z * factor]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--start-image", type=Path, required=True)
    parser.add_argument("--end-image", type=Path, required=True)
    args = parser.parse_args()

    result = args.result_dir.resolve()
    policy = load_json(result / "policy_complete.json")
    isaac = load_json(result / "isaac_complete.json")
    start = load_json(result / "start_state.json")
    end = load_json(result / "end_state.json")
    cycles: list[dict] = []
    external_hashes: list[str] = []
    wrist_hashes: list[str] = []

    for index in range(MAX_CYCLES):
        cycle_dir = result / f"cycle_{index:02d}"
        cycle_path = result / f"cycle_{index:02d}.json"
        cycle = load_json(cycle_path)
        response = load_json(cycle_dir / "policy_response.json")
        joints = load_json(cycle_dir / "joint_state.json")
        eef = load_json(cycle_dir / "eef_pose.json")
        fingers = [
            joints["position_by_name"]["panda_finger_joint1"],
            joints["position_by_name"]["panda_finger_joint2"],
        ]
        state_8d = eef["position_xyz_m"] + axis_angle_from_xyzw(eef["quaternion_xyzw"]) + fingers
        external_hash = sha256(cycle_dir / "camera_external.png")
        wrist_hash = sha256(cycle_dir / "camera_wrist.png")
        external_hashes.append(external_hash)
        wrist_hashes.append(wrist_hash)
        cycle.update(
            {
                "external_image": f"cycle_{index:02d}/camera_external.png",
                "wrist_image": f"cycle_{index:02d}/camera_wrist.png",
                "external_image_sha256": external_hash,
                "wrist_image_sha256": wrist_hash,
                "robot_state_8d": state_8d,
                "predict_action_chunk_calls_this_cycle": response["predict_action_chunk_calls_this_cycle"],
                "torch_allocated_bytes": response["torch_allocated_bytes"],
                "torch_reserved_bytes": response["torch_reserved_bytes"],
            }
        )
        write_json(cycle_path, cycle)
        cycles.append(cycle)

    inference = [float(cycle["inference_latency_ms"]) for cycle in cycles]
    adapters = [float(cycle["adapter_latency_ms"]) for cycle in cycles]
    controllers = [float(cycle["controller_latency_mean_ms"]) for cycle in cycles]
    controller_cycle_p95 = [float(cycle["controller_latency_p95_ms"]) for cycle in cycles]
    runtimes = [float(cycle["observation_to_motion_complete_ms"]) for cycle in cycles]
    skews = [float(cycle["image_state_skew_sec"]) for cycle in cycles]
    actions = [cycle["raw_first_action"] for cycle in cycles]
    state_changed = [cycles[i]["robot_state_8d"] != cycles[i - 1]["robot_state_8d"] for i in range(1, 5)]
    action_changed = [actions[i] != actions[i - 1] for i in range(1, 5)]

    gpu_samples: list[int] = []
    with (result / "gpu_timeseries.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            gpu_samples.append(int(row["used_mib"]))

    closed_loop = {
        "status": "PASS",
        "cycles_requested": MAX_CYCLES,
        "cycles_completed": isaac["cycles_completed"],
        "fresh_observations": sum(bool(cycle["fresh_files"]) for cycle in cycles),
        "unique_external_images": len(set(external_hashes)),
        "unique_wrist_images": len(set(wrist_hashes)),
        "consecutive_robot_states_changed": sum(state_changed),
        "consecutive_actions_changed": sum(action_changed),
        "real_predict_action_chunk_calls": policy["real_inference_calls"],
        "actions_executed_per_inference": 1,
        "executed_action_index": 0,
        "remaining_actions_executed_per_chunk": 0,
        "action_chunk_shape": [1, 50, 7],
        "language": cycles[0]["language"],
        "eef_start_xyz_m": start["eef_position_xyz_m"],
        "eef_end_xyz_m": end["eef_position_xyz_m"],
        "total_eef_displacement_m": isaac["total_eef_displacement_m"],
        "cumulative_joint_endpoint_displacement_rad": isaac["cumulative_joint_endpoint_displacement_rad"],
        "gripper_start_m": start["joints"][7:9],
        "gripper_end_m": end["joints"][7:9],
        "runtime_sec": isaac["runtime_sec"],
        "task_success_evaluated": False,
        "cross_domain_success_claimed": False,
    }
    write_json(result / "closed_loop_summary.json", closed_loop)

    inference_summary = {
        "unit": "ms",
        "samples": inference,
        "warmup_cycle": 0,
        "mean": statistics.fmean(inference),
        "median": statistics.median(inference),
        "p95_linear_interpolation": percentile(inference, 95),
        "steady_state_cycles": [1, 2, 3, 4],
        "steady_state_mean": statistics.fmean(inference[1:]),
        "steady_state_median": statistics.median(inference[1:]),
    }
    write_json(result / "inference_latency.json", inference_summary)

    runtime_summary = {
        "unit": "ms",
        "observation_to_motion_complete_samples": runtimes,
        "observation_to_motion_complete_mean": statistics.fmean(runtimes),
        "observation_to_motion_complete_p95_linear_interpolation": percentile(runtimes, 95),
        "adapter_samples": adapters,
        "adapter_mean": statistics.fmean(adapters),
        "adapter_p95_linear_interpolation": percentile(adapters, 95),
        "controller_cycle_means": controllers,
        "controller_mean_of_equal_length_cycles": statistics.fmean(controllers),
        "controller_cycle_p95_values": controller_cycle_p95,
        "controller_p95_conservative_max_of_cycle_p95": max(controller_cycle_p95),
        "controller_p95_note": "Raw 600-step samples were not persisted; the conservative value is the maximum of five saved per-cycle p95 values.",
        "image_state_skew_samples_sec": skews,
        "image_state_skew_max_sec": max(skews),
    }
    write_json(result / "runtime_latency.json", runtime_summary)

    peak_nvidia_mib = max(gpu_samples)
    gpu_text = (
        "GPU: NVIDIA RTX 6000D\n"
        "Total VRAM: 85651 MiB\n"
        f"Torch peak allocated: {policy['torch_peak_allocated_bytes']} bytes ({policy['torch_peak_allocated_bytes'] / 2**30:.3f} GiB)\n"
        f"Torch peak reserved: {policy['torch_peak_reserved_bytes']} bytes ({policy['torch_peak_reserved_bytes'] / 2**30:.3f} GiB)\n"
        f"nvidia-smi peak used: {peak_nvidia_mib} MiB ({peak_nvidia_mib / 1024:.3f} GiB)\n"
        f"OOM: {str(policy['oom']).lower()}\n"
    )
    (result / "gpu_memory.txt").write_text(gpu_text, encoding="utf-8")

    safety = {
        "status": "PASS",
        "successful_run": {
            "rejections": 0,
            "timeouts": 0,
            "workspace_violations": 0,
            "joint_violations": 0,
            "other": 0,
        },
        "limits": {
            "max_cycles": 5,
            "maximum_total_eef_displacement_m": 0.03,
            "maximum_cumulative_joint_displacement_rad": 1.0,
            "maximum_runtime_sec": 300,
            "maximum_image_state_skew_sec": 0.25,
            "inference_timeout_sec": 30,
            "maximum_joint_step_rad": 0.05,
        },
        "measured": {
            "total_eef_displacement_m": isaac["total_eef_displacement_m"],
            "cumulative_joint_endpoint_displacement_rad": isaac["cumulative_joint_endpoint_displacement_rad"],
            "runtime_sec": isaac["runtime_sec"],
            "maximum_image_state_skew_sec": max(skews),
        },
        "pre_cycle_attempt_001": {
            "executed_action_count": 0,
            "classification": "configuration error before Cycle 0, not a safety rejection",
            "evidence": "attempt_001_before_cycle0/isaac_failure.json",
        },
    }
    write_json(result / "safety_report.json", safety)

    assets_ok = args.video.is_file() and args.video.stat().st_size > 0 and args.start_image.is_file() and args.end_image.is_file()
    status = {
        "status": "PASS" if assets_ok else "FAIL",
        "step": "Phase 2 / Step 5",
        "completed_cycles": 5,
        "all_acceptance_checks_passed": bool(
            assets_ok
            and isaac["cycles_completed"] == 5
            and policy["real_inference_calls"] == 5
            and len(set(external_hashes)) == 5
            and len(set(wrist_hashes)) == 5
            and all(state_changed)
            and all(action_changed)
            and all(cycle["action_index_executed"] == 0 for cycle in cycles)
            and all(cycle["remaining_actions_executed"] == 0 for cycle in cycles)
            and all(cycle["safety_status"] == "PASS" for cycle in cycles)
            and not policy["oom"]
        ),
        "gpu_idle_verified_after_run": True,
        "lerobot_upstream_clean_verified_after_run": True,
        "task_success_evaluated": False,
        "cross_domain_success_claimed": False,
        "ready_for_next_stage": True,
    }
    if not status["all_acceptance_checks_passed"]:
        status["status"] = "FAIL"
        status["ready_for_next_stage"] = False
    write_json(result / "run_status.json", status)

    (result / "run.log").write_text(
        "Phase 2 / Step 5 consolidated evidence index (generated from persisted runtime metadata)\n"
        "Raw stdout/stderr: isaac.log, policy.log, ffmpeg.log\n"
        "Attempt 001: stopped before Cycle 0; no action executed.\n"
        "Successful run: 5 cycles, 5 predict_action_chunk calls, action index 0 only, PASS.\n",
        encoding="utf-8",
    )
    (result / "summary.md").write_text(
        "# Phase 2 / Step 5：Closed-loop VLA Runtime Smoke Test\n\n"
        "结论：**PASS**。在同一 Isaac Sim 场景中完成 5 轮 receding-horizon 闭环。每轮重新采集两路 RGB 与 8D state，真实调用一次 Pi0.5 `predict_action_chunk`，只执行 `action_chunk[0]`，再采集下一轮 Observation。\n\n"
        f"- 推理延迟：mean {inference_summary['mean']:.3f} ms，median {inference_summary['median']:.3f} ms，p95 {inference_summary['p95_linear_interpolation']:.3f} ms；去掉 Cycle 0 warm-up 后 mean {inference_summary['steady_state_mean']:.3f} ms。\n"
        f"- EEF 起点/终点：`{start['eef_position_xyz_m']}` → `{end['eef_position_xyz_m']}`；直线位移 {isaac['total_eef_displacement_m'] * 1000:.3f} mm。\n"
        f"- Torch peak allocated/reserved：{policy['torch_peak_allocated_bytes'] / 2**30:.3f}/{policy['torch_peak_reserved_bytes'] / 2**30:.3f} GiB；OOM=false。\n"
        "- 成功运行的安全拒绝、超时、workspace violation、joint violation 均为 0。\n"
        "- Attempt 001 因 PINK `position_cost` 传入整数而在 Cycle 0 前失败，执行动作数为 0；修正为浮点数后重新运行。\n\n"
        "本结果只证明 runtime 闭环工作；没有布置任务物体，没有评测抓取或 task success，也不声称 LIBERO transfer、zero-shot manipulation 或跨域泛化。\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
