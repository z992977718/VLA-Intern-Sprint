#!/usr/bin/env python3
"""One-observation Pi0.5 + LIBERO migration smoke test.

This diagnostic deliberately does not train, step the environment, create an
optimizer, or write into any existing experiment directory.
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

# Registers the pi05 policy type before PreTrainedConfig loads config.json.
import lerobot.policies.pi05  # noqa: F401
from lerobot.configs.policies import PreTrainedConfig
from lerobot.envs.factory import make_env, make_env_config, make_env_pre_post_processors
from lerobot.envs.utils import NEW_ROLLOUT_OPTION, preprocess_observation
from lerobot.policies.factory import make_policy, make_pre_post_processors


def schema(value: Any) -> dict[str, Any]:
    if isinstance(value, torch.Tensor):
        return {
            "kind": "torch.Tensor",
            "shape": list(value.shape),
            "dtype": str(value.dtype),
            "device": str(value.device),
            "finite": bool(torch.isfinite(value).all()) if value.is_floating_point() else None,
        }
    if isinstance(value, np.ndarray):
        return {
            "kind": "numpy.ndarray",
            "shape": list(value.shape),
            "dtype": str(value.dtype),
            "finite": bool(np.isfinite(value).all()) if np.issubdtype(value.dtype, np.floating) else None,
        }
    if isinstance(value, list):
        return {"kind": "list", "length": len(value), "sample": str(value[0])[:240] if value else None}
    if isinstance(value, dict):
        return {"kind": "dict", "keys": sorted(value)}
    return {"kind": type(value).__name__}


def nvidia_smi() -> str:
    return subprocess.run(["nvidia-smi"], text=True, capture_output=True, check=False).stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--suite", default="libero_10")
    parser.add_argument("--task-id", type=int, default=0)
    args = parser.parse_args()

    checkpoint = args.checkpoint.resolve()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing directory: {output_dir}")
    if not (checkpoint / "config.json").is_file() or not (checkpoint / "model.safetensors").is_file():
        raise FileNotFoundError(f"Not a complete checkpoint: {checkpoint}")
    output_dir.mkdir(parents=True)
    (output_dir / "nvidia_smi_before.txt").write_text(nvidia_smi(), encoding="utf-8")

    env_cfg = make_env_config(
        "libero",
        task=args.suite,
        task_ids=[args.task_id],
        observation_height=360,
        observation_width=360,
        init_states=True,
        hard_reset=True,
        control_mode="relative",
        max_parallel_tasks=1,
    )
    policy_cfg = PreTrainedConfig.from_pretrained(str(checkpoint))
    policy_cfg.pretrained_path = checkpoint
    policy_cfg.device = "cuda"
    policy_cfg.dtype = "bfloat16"
    policy_cfg.use_amp = False

    env = None
    started = time.perf_counter()
    try:
        env = make_env(env_cfg, n_envs=1, use_async_envs=False)[args.suite][args.task_id]
        raw_observation, _ = env.reset(seed=[1000], options={NEW_ROLLOUT_OPTION: True})
        task_description = str(env.call("task_description")[0])

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
        env_preprocessor, _ = make_env_pre_post_processors(env_cfg, policy_cfg)

        observation = preprocess_observation(raw_observation)
        observation["task"] = [task_description]
        canonical_observation = env_preprocessor(observation)
        model_input = preprocessor(copy.deepcopy(canonical_observation))

        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
        inference_start = time.perf_counter()
        with torch.inference_mode():
            normalized_chunk = policy.predict_action_chunk(model_input)
        torch.cuda.synchronize()
        inference_ms = (time.perf_counter() - inference_start) * 1000.0
        action_chunk = postprocessor(normalized_chunk).detach().cpu()

        report = {
            "purpose": "one reset and one real predict_action_chunk call; no env.step, training, or optimizer",
            "checkpoint": str(checkpoint),
            "suite": args.suite,
            "task_id": args.task_id,
            "task_description": task_description,
            "raw_observation": {key: schema(value) for key, value in raw_observation.items()},
            "canonical_observation": {key: schema(value) for key, value in canonical_observation.items()},
            "model_input": {key: schema(value) for key, value in model_input.items()},
            "policy": {
                "type": policy_cfg.type,
                "dtype": policy_cfg.dtype,
                "chunk_size": policy_cfg.chunk_size,
                "n_action_steps": policy_cfg.n_action_steps,
            },
            "action_chunk": {
                "shape": list(action_chunk.shape),
                "dtype": str(action_chunk.dtype),
                "finite": bool(torch.isfinite(action_chunk).all()),
                "min": float(action_chunk.min()),
                "max": float(action_chunk.max()),
            },
            "single_call_latency_ms": inference_ms,
            "torch_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "torch_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
            "gpu": torch.cuda.get_device_name(0),
            "cuda": torch.version.cuda,
            "bf16_supported": torch.cuda.is_bf16_supported(),
            "oom": False,
            "env_step_executed": False,
        }
        (output_dir / "smoke_test.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        np.save(output_dir / "action_chunk.npy", action_chunk.numpy())
        print(json.dumps(report, indent=2), flush=True)
    finally:
        if env is not None:
            env.close()
        (output_dir / "nvidia_smi_after.txt").write_text(nvidia_smi(), encoding="utf-8")
        (output_dir / "wall_time_seconds.txt").write_text(f"{time.perf_counter() - started:.6f}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
