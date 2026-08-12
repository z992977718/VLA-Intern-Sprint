#!/usr/bin/env python3
"""Run a profiled Pi0.5 LIBERO evaluation without modifying LeRobot source."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import subprocess
import time
import types
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import torch

from lerobot.configs.policies import PreTrainedConfig
from lerobot.envs.factory import make_env, make_env_config, make_env_pre_post_processors
from lerobot.policies.factory import make_policy, make_pre_post_processors
from lerobot.scripts import lerobot_eval
from lerobot.utils.random_utils import set_seed


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=np.float64), q))


def write_nvidia_smi(path: Path) -> None:
    result = subprocess.run(["nvidia-smi"], text=True, capture_output=True, check=False)
    path.write_text(result.stdout + result.stderr, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--suite", default="libero_10")
    parser.add_argument("--task-id", type=int, default=0)
    parser.add_argument("--episodes", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--dtype", choices=("bfloat16", "float32"), default="bfloat16")
    parser.add_argument("--n-action-steps", type=int, default=10)
    parser.add_argument("--observation-height", type=int, default=360)
    parser.add_argument("--observation-width", type=int, default=360)
    parser.add_argument("--init-state-start", type=int, default=0)
    args = parser.parse_args()

    if args.episodes < 1:
        raise ValueError("--episodes must be positive")
    if args.init_state_start < 0:
        raise ValueError("--init-state-start must be non-negative")

    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation directory: {output_dir}")
    output_dir.mkdir(parents=True)
    videos_dir = output_dir / "videos"
    write_nvidia_smi(output_dir / "nvidia_smi_before.txt")

    checkpoint = Path(args.checkpoint).resolve()
    if not (checkpoint / "config.json").is_file() or not (checkpoint / "model.safetensors").is_file():
        raise FileNotFoundError(f"Not a LeRobot pretrained checkpoint: {checkpoint}")

    env_cfg = make_env_config(
        "libero",
        task=args.suite,
        task_ids=[args.task_id],
        observation_height=args.observation_height,
        observation_width=args.observation_width,
        init_states=True,
        hard_reset=True,
        control_mode="relative",
        max_parallel_tasks=1,
    )

    policy_cfg = PreTrainedConfig.from_pretrained(str(checkpoint))
    policy_cfg.pretrained_path = checkpoint
    policy_cfg.device = "cuda"
    policy_cfg.dtype = args.dtype
    policy_cfg.use_amp = False
    policy_cfg.n_action_steps = args.n_action_steps

    set_seed(args.seed)
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True

    envs = make_env(env_cfg, n_envs=1, use_async_envs=False)
    env = envs[args.suite][args.task_id]
    individual_envs = getattr(env, "envs", None)
    if individual_envs is None or len(individual_envs) != 1:
        raise RuntimeError("Expected one synchronous LIBERO sub-environment")
    libero_env = individual_envs[0].unwrapped
    if not hasattr(libero_env, "init_state_id") or not hasattr(libero_env, "_init_states"):
        raise RuntimeError("Current LIBERO environment does not expose fixed init-state selection")
    init_state_count = len(libero_env._init_states)
    if args.init_state_start + args.episodes > init_state_count:
        raise ValueError(
            f"Requested init states {args.init_state_start}-"
            f"{args.init_state_start + args.episodes - 1}, but only {init_state_count} are available"
        )
    libero_env.init_state_id = args.init_state_start
    if int(libero_env.init_state_id) != args.init_state_start:
        raise RuntimeError("Failed to set the requested LIBERO init-state start index")
    policy = make_policy(cfg=policy_cfg, env_cfg=env_cfg, rename_map={})
    policy.eval()

    preprocessor, postprocessor = make_pre_post_processors(
        policy_cfg=policy_cfg,
        pretrained_path=str(checkpoint),
        preprocessor_overrides={
            "device_processor": {"device": str(policy.config.device)},
            "rename_observations_processor": {"rename_map": {}},
        },
    )
    env_preprocessor, env_postprocessor = make_env_pre_post_processors(env_cfg, policy_cfg)

    try:
        task_description = str(env.call("task_description")[0])
    except Exception:
        task_description = ""

    inference_rows: list[dict[str, Any]] = []
    rollout_profiles: list[dict[str, Any]] = []
    original_rollout = lerobot_eval.rollout

    def profiled_rollout(*rollout_args: Any, **rollout_kwargs: Any):
        rollout_policy = rollout_kwargs.get("policy")
        if rollout_policy is None and len(rollout_args) > 1:
            rollout_policy = rollout_args[1]
        seeds = list(rollout_kwargs.get("seeds") or [None])
        if len(seeds) != 1:
            raise ValueError("Profiled evaluation requires batch_size=1")

        episode_index = len(rollout_profiles)
        init_state_id = args.init_state_start + episode_index
        original_predict = rollout_policy.predict_action_chunk
        episode_latencies: list[float] = []

        def timed_predict(self: Any, *predict_args: Any, **predict_kwargs: Any):
            torch.cuda.synchronize()
            started = time.perf_counter()
            result = original_predict(*predict_args, **predict_kwargs)
            torch.cuda.synchronize()
            latency_ms = (time.perf_counter() - started) * 1000.0
            model_call_index = len(episode_latencies)
            episode_latencies.append(latency_ms)
            inference_rows.append(
                {
                    "episode_index": episode_index,
                    "init_state_id": init_state_id,
                    "seed": seeds[0],
                    "model_call_index": model_call_index,
                    "control_step": model_call_index * args.n_action_steps,
                    "latency_ms": latency_ms,
                }
            )
            return result

        rollout_policy.predict_action_chunk = types.MethodType(timed_predict, rollout_policy)
        rollout_started = time.perf_counter()
        try:
            rollout_data = original_rollout(*rollout_args, **rollout_kwargs)
        finally:
            rollout_policy.predict_action_chunk = original_predict
        rollout_wall_s = time.perf_counter() - rollout_started

        done = rollout_data["done"][0]
        done_positions = torch.nonzero(done, as_tuple=False)
        episode_length = int(done_positions[0].item() + 1) if len(done_positions) else int(done.shape[0])
        rollout_profiles.append(
            {
                "episode_index": episode_index,
                "init_state_id": init_state_id,
                "seed": seeds[0],
                "episode_length": episode_length,
                "rollout_wall_s": rollout_wall_s,
                "model_inference_calls": len(episode_latencies),
                "mean_model_inference_ms": statistics.fmean(episode_latencies) if episode_latencies else None,
                "median_model_inference_ms": statistics.median(episode_latencies) if episode_latencies else None,
                "p95_model_inference_ms": percentile(episode_latencies, 95),
            }
        )
        return rollout_data

    lerobot_eval.rollout = profiled_rollout
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    eval_started = time.perf_counter()
    try:
        with torch.no_grad():
            info = lerobot_eval.eval_policy(
                env=env,
                policy=policy,
                env_preprocessor=env_preprocessor,
                env_postprocessor=env_postprocessor,
                preprocessor=preprocessor,
                postprocessor=postprocessor,
                n_episodes=args.episodes,
                max_episodes_rendered=args.episodes,
                videos_dir=videos_dir,
                return_episode_data=False,
                start_seed=args.seed,
            )
        torch.cuda.synchronize()
    finally:
        lerobot_eval.rollout = original_rollout
        env.close()
    eval_wall_s = time.perf_counter() - eval_started

    peak_allocated = torch.cuda.max_memory_allocated()
    peak_reserved = torch.cuda.max_memory_reserved()
    all_latencies = [float(row["latency_ms"]) for row in inference_rows]

    episode_rows: list[dict[str, Any]] = []
    for metric, profile in zip(info["per_episode"], rollout_profiles, strict=True):
        episode_index = int(metric["episode_ix"])
        video_path = str(videos_dir / f"eval_episode_{episode_index}.mp4")
        success = bool(metric["success"])
        if success:
            termination_reason = "success"
            failure_category = "none"
            failure_description = ""
        elif profile["episode_length"] >= (520 if args.suite == "libero_10" else math.inf):
            termination_reason = "episode_horizon_exhausted"
            failure_category = "episode_horizon_exhausted"
            failure_description = "No LIBERO success before the configured episode horizon."
        else:
            termination_reason = "environment_termination_without_success"
            failure_category = "other_environment_termination"
            failure_description = "The environment terminated before success and before the episode horizon."
        episode_rows.append(
            {
                "episode_index": episode_index,
                "init_state_id": profile["init_state_id"],
                "seed": metric["seed"],
                "suite": args.suite,
                "task_id": args.task_id,
                "task_description": task_description,
                "checkpoint": str(checkpoint),
                "success": success,
                "episode_length": profile["episode_length"],
                "termination_reason": termination_reason,
                "failure_category": failure_category,
                "failure_description": failure_description,
                "sum_reward": metric["sum_reward"],
                "max_reward": metric["max_reward"],
                "rollout_wall_s": profile["rollout_wall_s"],
                "model_inference_calls": profile["model_inference_calls"],
                "mean_model_inference_ms": profile["mean_model_inference_ms"],
                "median_model_inference_ms": profile["median_model_inference_ms"],
                "p95_model_inference_ms": profile["p95_model_inference_ms"],
                "video_path": video_path,
            }
        )

    success_count = sum(int(row["success"]) for row in episode_rows)
    episode_lengths = [int(row["episode_length"]) for row in episode_rows]
    summary = {
        "checkpoint": str(checkpoint),
        "suite": args.suite,
        "task_id": args.task_id,
        "task_description": task_description,
        "episodes": args.episodes,
        "seed_start": args.seed,
        "seeds": [args.seed + i for i in range(args.episodes)],
        "init_state_start": args.init_state_start,
        "init_state_count_available": init_state_count,
        "init_state_ids": [args.init_state_start + i for i in range(args.episodes)],
        "success_count": success_count,
        "success_rate": success_count / args.episodes,
        "episode_limit": 520 if args.suite == "libero_10" else None,
        "mean_episode_length": statistics.fmean(episode_lengths),
        "median_episode_length": statistics.median(episode_lengths),
        "min_episode_length": min(episode_lengths),
        "max_episode_length": max(episode_lengths),
        "eval_wall_s": eval_wall_s,
        "official_eval_s": info["aggregated"]["eval_s"],
        "model_inference_calls": len(all_latencies),
        "mean_model_inference_ms": statistics.fmean(all_latencies) if all_latencies else None,
        "median_model_inference_ms": statistics.median(all_latencies) if all_latencies else None,
        "p50_model_inference_ms": statistics.median(all_latencies) if all_latencies else None,
        "p95_model_inference_ms": percentile(all_latencies, 95),
        "peak_allocated_bytes": peak_allocated,
        "peak_allocated_gib": peak_allocated / 1024**3,
        "peak_reserved_bytes": peak_reserved,
        "peak_reserved_gib": peak_reserved / 1024**3,
        "gpu_name": torch.cuda.get_device_name(0),
        "total_vram_gib": torch.cuda.get_device_properties(0).total_memory / 1024**3,
        "torch_version": torch.__version__,
        "cuda_version": torch.version.cuda,
        "policy_dtype": policy.config.dtype,
        "policy_use_amp": policy.config.use_amp,
        "n_action_steps": policy.config.n_action_steps,
        "batch_size": 1,
        "observation_height": args.observation_height,
        "observation_width": args.observation_width,
        "control_mode": "relative",
        "init_states": True,
        "hard_reset": True,
        "oom": False,
    }

    resolved_config = {
        "arguments": vars(args),
        "environment": asdict(env_cfg),
        "policy": {
            "type": policy.config.type,
            "dtype": policy.config.dtype,
            "use_amp": policy.config.use_amp,
            "device": str(policy.config.device),
            "n_action_steps": policy.config.n_action_steps,
            "chunk_size": policy.config.chunk_size,
            "num_inference_steps": policy.config.num_inference_steps,
            "empty_cameras": policy.config.empty_cameras,
        },
    }
    (output_dir / "config.json").write_text(json.dumps(resolved_config, indent=2, default=str) + "\n", encoding="utf-8")
    (output_dir / "eval_info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    with (output_dir / "episodes.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(episode_rows[0]))
        writer.writeheader()
        writer.writerows(episode_rows)
    with (output_dir / "latency.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(inference_rows[0]))
        writer.writeheader()
        writer.writerows(inference_rows)

    failures = [row for row in episode_rows if not row["success"]]
    failure_lines = ["# Failure cases", ""]
    if not failures:
        failure_lines.append("No failed episodes in this evaluation.")
    else:
        failure_lines.extend(
            f"- Episode {row['episode_index']}, init state {row['init_state_id']}, seed {row['seed']}: "
            f"{row['failure_description']} "
            f"Termination: `{row['termination_reason']}` at {row['episode_length']} steps. "
            f"Video: `{row['video_path']}`"
            for row in failures
        )
    (output_dir / "failure_cases.md").write_text("\n".join(failure_lines) + "\n", encoding="utf-8")
    write_nvidia_smi(output_dir / "nvidia_smi_after.txt")

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
