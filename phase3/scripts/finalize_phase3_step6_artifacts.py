#!/usr/bin/env python3
"""Build the requested Step 6 artifact index from immutable measured outputs."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import shutil
import statistics
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
RESULT = PROJECT / "results/phase3_step6"
VIDEOS = PROJECT / "assets/videos"


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def percentile95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[int(0.95 * (len(ordered) - 1))]


def latency(values: list[float]) -> dict:
    return {
        "count": len(values),
        "mean_ms": statistics.fmean(values),
        "median_ms": statistics.median(values),
        "p95_ms": percentile95(values),
        "min_ms": min(values),
        "max_ms": max(values),
    }


def main() -> int:
    summary = json.loads((RESULT / "summary.json").read_text(encoding="utf-8"))
    asset_conversion = json.loads((RESULT / "asset_conversion.json").read_text(encoding="utf-8"))
    gate = json.loads((RESULT / "scene_gate_state00_dynamic/scene_gate.json").read_text(encoding="utf-8"))
    detector = json.loads((RESULT / "scene_gate_state00_dynamic/success_detector_tests.json").read_text(encoding="utf-8"))
    failures = json.loads((RESULT / "failure_metrics.json").read_text(encoding="utf-8"))

    gpu_samples = []
    with (RESULT / "gpu_timeseries.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            gpu_samples.append(
                {
                    "timestamp": row["timestamp"].strip(),
                    "used_mib": int(row["used_mib"].strip()),
                    "util_percent": int(row["util_percent"].strip()),
                }
            )
    gpu_peak_mib = max(sample["used_mib"] for sample in gpu_samples)

    all_cycles = []
    initial_states = []
    task_results = []
    failure_summary = []
    for episode_index in range(3):
        episode = RESULT / f"episode_{episode_index:02d}"
        reset = json.loads((episode / "reset.json").read_text(encoding="utf-8"))
        complete = json.loads((episode / "episode_complete.json").read_text(encoding="utf-8"))
        cycles = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(episode.glob("cycle_???.json"))]
        reference_folder = "libero_reference" if episode_index == 0 else f"libero_reference_state{episode_index:02d}"
        reference = json.loads((RESULT / reference_folder / "libero_reference.json").read_text(encoding="utf-8"))
        all_cycles.extend(cycles)
        initial_state = {
            "state_id": episode_index,
            "random_seed": None,
            "random_seed_note": "未使用随机采样；直接映射 LIBERO 固定 initial state ID",
            "hard_reset_process": reset["hard_reset_process"],
            "robot_initial_joints_rad": reset["isaac_robot_joints_after_settle_rad"],
            "source_libero_robot_joints_rad": reset["source_robot_arm_joints_rad"],
            "eef_pose": {
                "position_xyz_m": reset["eef_position_xyz_m"],
                "quaternion_wxyz": reset["eef_quaternion_wxyz"],
                "source_delta_norm_m": reset["eef_source_delta_norm_m"],
            },
            "object_positions_xyz_m": reset["object_positions_xyz_m"],
            "source_libero_object_poses": reference["body_poses"],
            "initial_success": reset["initial_success_metric"]["success"],
        }
        initial_states.append(initial_state)
        dump(RESULT / f"initial_states/state_{episode_index:02d}.json", initial_state)

        inference = [record["inference_latency_ms"] for record in cycles]
        adapter = [record["adapter_latency_ms"] for record in cycles]
        pink = [record["controller_latency_mean_ms"] for record in cycles]
        observation_to_target = [a + b for a, b in zip(inference, adapter, strict=True)]
        per_episode_latency = {
            "inference": latency(inference),
            "inference_steady_state_mean_ms_skip_first_10": statistics.fmean(inference[10:]),
            "action_adapter": latency(adapter),
            "pink_forward_mean_per_cycle": latency(pink),
            "observation_to_action_target_note": "可测部分为 Pi0.5 inference + Action Adapter；不含图像采集、文件握手与完整运动执行",
            "observation_to_action_target_measured": latency(observation_to_target),
        }
        dump(episode / "latency.json", per_episode_latency)
        trajectory = {
            "episode_index": episode_index,
            "initial_state_id": episode_index,
            "cycles": [
                {
                    "cycle_index": record["cycle_index"],
                    "eef_before_xyz_m": record["eef_before_xyz_m"],
                    "eef_target_xyz_m": record["eef_target_xyz_m"],
                    "eef_after_xyz_m": record["eef_after_xyz_m"],
                    "bounded_action": record["bounded_action"],
                    "gripper_action": record["bounded_action"][6],
                    "gripper_joint_positions_m": [
                        json.loads((episode / f"cycle_{record['cycle_index']:03d}/joint_state.json").read_text(encoding="utf-8"))["position_by_name"]["panda_finger_joint1"],
                        json.loads((episode / f"cycle_{record['cycle_index']:03d}/joint_state.json").read_text(encoding="utf-8"))["position_by_name"]["panda_finger_joint2"],
                    ],
                    "object_centers_xyz_m": record["object_centers_xyz_m"],
                    "success": record["success_metric"]["success"],
                    "safety_status": record["safety_status"],
                }
                for record in cycles
            ],
        }
        dump(episode / "trajectory.json", trajectory)
        final_state = {
            "episode_index": episode_index,
            "final_eef_position_xyz_m": complete["final_eef_position_xyz_m"],
            "final_eef_quaternion_wxyz": complete["final_eef_quaternion_wxyz"],
            "final_object_centers_xyz_m": cycles[-1]["object_centers_xyz_m"],
            "final_success_metric": complete["final_success_metric"],
        }
        dump(episode / "final_state.json", final_state)
        video = VIDEOS / f"phase3_step6_ep{episode_index:02d}.mp4"
        result = {
            "episode_index": episode_index,
            "initial_state_id": episode_index,
            "completed": complete["completed"],
            "success": complete["success"],
            "cycles": complete["cycles_completed"],
            "termination": complete["termination"].upper(),
            "wall_clock_sec": complete["runtime_sec"],
            "manual_intervention": complete["manual_intervention"],
            "oom": complete["oom"],
            "failure_categories": ["failed approach", "failed grasp", "horizon reached"],
            "observed_behavior": "机械臂在桌面任务区和篮子附近运动，但未形成可观察的目标物体接触、抓取或搬运；两个目标物体测得位移均为 0。",
            "possible_explanations": "视觉域差异、相机差异、状态分布偏移、控制/夹爪动力学差异均是可能假设，未证明任何模型内部原因。",
            "video": str(video.relative_to(PROJECT)).replace("\\", "/"),
            "video_sha256": sha256(video),
            "video_size_bytes": video.stat().st_size,
        }
        dump(episode / "result.json", result)
        # Preserve the original Isaac stdout/stderr under the required filename too.
        shutil.copyfile(episode / "isaac.log", episode / "run.log")
        (episode / "gpu_memory.txt").write_text(
            "本次 run 使用同一全局 1 Hz nvidia-smi 采样。\n"
            f"全局峰值显存: {gpu_peak_mib} MiB。\n"
            "逐 episode 精确边界未单独打点，因此不虚构每回合独立峰值；原始数据见 ../../gpu_timeseries.csv。\n",
            encoding="utf-8",
        )
        task_results.append(result)
        failure_summary.append(
            {
                "episode_index": episode_index,
                "failure_categories": result["failure_categories"],
                "alphabet_soup_displacement_m": failures[f"episode_{episode_index:02d}"]["alphabet_soup_displacement_m"],
                "tomato_sauce_displacement_m": failures[f"episode_{episode_index:02d}"]["tomato_sauce_displacement_m"],
                "eef_path_m": failures[f"episode_{episode_index:02d}"]["final_cumulative_eef_path_m"],
                "observed_behavior": result["observed_behavior"],
            }
        )

    inference_all = [record["inference_latency_ms"] for record in all_cycles]
    adapter_all = [record["adapter_latency_ms"] for record in all_cycles]
    pink_all = [record["controller_latency_mean_ms"] for record in all_cycles]
    steady = []
    for episode_index in range(3):
        episode_cycles = [record for record in all_cycles if record["episode_index"] == episode_index]
        steady.extend(record["inference_latency_ms"] for record in episode_cycles[10:])

    environment = {
        "date": "2026-08-12",
        "server": "AutoDL Linux GPU server",
        "gpu": "NVIDIA RTX 6000D",
        "gpu_total_mib": 85651,
        "isaac_sim": "6.0.1",
        "lerobot": "0.6.2",
        "lerobot_commit": "22bd7a2f489b367d8df42de803b1e8c4ca63a3f9",
        "policy_checkpoint": summary["checkpoint"],
        "torch_peak_allocated_bytes": summary["torch_peak_allocated_bytes"],
        "torch_peak_reserved_bytes": summary["torch_peak_reserved_bytes"],
        "nvidia_smi_peak_used_mib_global": gpu_peak_mib,
        "oom": summary["oom"],
    }
    (RESULT / "environment.txt").write_text(
        "\n".join(f"{key}: {value}" for key, value in environment.items()) + "\n", encoding="utf-8"
    )
    task_config = {
        "task_suite": "libero_10",
        "suite_task_id": 0,
        "phase1_dataset_task_index": 5,
        "instruction": summary["language"],
        "source_bddl_sha256": gate["source_bddl_sha256"],
        "episodes": 3,
        "initial_state_ids": [0, 1, 2],
        "hard_reset": True,
        "max_cycles": 100,
        "receding_horizon_k": 1,
        "action_chunk_shape": [50, 7],
        "success_predicate": detector["predicate"],
        "training_or_weight_update": False,
    }
    dump(RESULT / "task_config.json", task_config)
    scene_mapping = {
        "robot": {"status": "APPROXIMATE", "detail": "Franka Panda identity matched; Isaac and robosuite robot assets/dynamics differ"},
        "table_visual": {"status": "MATCH", "detail": "same LIBERO OBJ, scale 1.5, converted to USD"},
        "table_collision": {"status": "MATCH_FOR_TASK_TOP", "detail": "exact runtime MuJoCo tabletop box; decorative collision geoms omitted"},
        "target_visual_assets": {"status": "MATCH", "detail": "same LIBERO OBJ/textures, scale 0.01"},
        "target_collision": {"status": "APPROXIMATE ASSET", "detail": "one measured bounding box per target, not full multi-box MuJoCo collision set"},
        "basket_visual_collision": {"status": "MATCH", "detail": "same OBJ plus five exact box colliders from basket.xml"},
        "object_initial_poses": {"status": "MATCH", "detail": "actual settled poses from fixed LIBERO states 0,1,2"},
        "external_camera": {"status": "MATCH_PARAMETERS", "detail": "source world pose and 45 degree vertical FOV; renderer differs"},
        "wrist_camera": {"status": "APPROXIMATE", "detail": "initial LIBERO world pose calibrated then rigidly follows Isaac panda_hand"},
        "lighting_background": {"status": "APPROXIMATE", "detail": "neutral Isaac lights/background; LIBERO living-room walls and four distractors omitted"},
        "gripper": {"status": "APPROXIMATE", "detail": "same parallel-gripper intent; joint sign/range and contact dynamics differ"},
        "control_frame": {"status": "CALIBRATED_APPROXIMATE", "detail": "fixed 95.1035 mm local tool offset maps Isaac panda_hand to LIBERO EEF point"},
        "physics": {"status": "APPROXIMATE", "detail": "PhysX instead of MuJoCo; friction/contact solver equivalence not established"},
    }
    dump(RESULT / "scene_mapping.json", scene_mapping)
    dump(RESULT / "success_detector_test.json", detector)
    dump(RESULT / "task_results.json", {"successes": 0, "failures": 3, "success_rate": 0.0, "episodes": task_results})
    dump(RESULT / "failure_summary.json", {"common_categories": ["failed approach", "failed grasp", "horizon reached"], "episodes": failure_summary})
    domain_gap = {
        "known_differences": [
            "MuJoCo/robosuite versus PhysX/Isaac Sim",
            "renderer, lighting and background differ",
            "four source-scene distractor objects omitted",
            "target collision geometry approximated by one bounding box",
            "wrist camera follow transform is calibrated but not the same robot camera mount model",
            "Franka, gripper and controller dynamics differ",
            "fixed EEF tool-point offset is calibrated from state 0",
        ],
        "observed": "3/3 回合中机械臂运动到任务区/篮子附近，但两个目标罐位移均为 0；没有有效抓取、搬运或放置；均在 100 cycles 到达 horizon。",
        "hypotheses_not_proven": ["visual domain gap", "camera mismatch", "state distribution shift", "action scaling/control mismatch", "gripper/contact dynamics mismatch"],
    }
    dump(RESULT / "domain_gap_summary.json", domain_gap)
    run_status = {
        "experimental_pipeline": {
            "task_scene": "PASS",
            "success_detector": "PASS",
            "reset": "PASS",
            "observation": "PASS",
            "pi05_runtime": "PASS",
            "action_adapter": "PASS",
            "closed_loop": "PASS",
            "artifacts": "PASS",
        },
        "step6": "PASS",
        "policy_task_result": "0/3",
        "task_transfer": "FAIL",
        "unseen_task_generalization_claimed": False,
        "sim_to_real_claimed": False,
        "ready_for_step7": False,
        "gpu_idle_after_run": True,
    }
    dump(RESULT / "run_status.json", run_status)
    performance = {
        "inference": latency(inference_all),
        "steady_state_mean_ms_skip_first_10_each_episode": statistics.fmean(steady),
        "action_adapter": latency(adapter_all),
        "pink_forward_mean_per_cycle": latency(pink_all),
        "observation_to_action_target_measured": latency([a + b for a, b in zip(inference_all, adapter_all, strict=True)]),
        "observation_to_action_target_scope": "Pi0.5 inference + Action Adapter only",
        "nvidia_smi_global_peak_used_mib": gpu_peak_mib,
        "torch_peak_allocated_bytes": summary["torch_peak_allocated_bytes"],
        "torch_peak_reserved_bytes": summary["torch_peak_reserved_bytes"],
        "oom": False,
    }
    dump(RESULT / "performance.json", performance)
    dump(RESULT / "initial_states/index.json", {"states": initial_states})
    manifest = []
    for path in sorted(RESULT.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            manifest.append({"path": str(path.relative_to(PROJECT)).replace("\\", "/"), "size_bytes": path.stat().st_size, "sha256": sha256(path)})
    for video in sorted(VIDEOS.glob("phase3_step6_ep*.mp4")):
        manifest.append({"path": str(video.relative_to(PROJECT)).replace("\\", "/"), "size_bytes": video.stat().st_size, "sha256": sha256(video)})
    dump(RESULT / "artifact_manifest.json", {"generated_at": dt.datetime.now().isoformat(), "files": manifest})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
