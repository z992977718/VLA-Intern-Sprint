#!/usr/bin/env python3
"""Step 4：只做一次 Pi0.5 inference，只准备 action_chunk[0]。"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import torch

from lerobot.configs.policies import PreTrainedConfig
from lerobot.envs.factory import make_env_config
from lerobot.policies.factory import make_policy, make_pre_post_processors

from action_adapter_step4 import SafetyConfig, adapt_libero_action
from policy_input_adapter import build_policy_input


def quat_wxyz_to_matrix(q: np.ndarray) -> np.ndarray:
    w, x, y, z = np.asarray(q, dtype=np.float64)
    return np.array([
        [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
        [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
        [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)],
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--language", default="move the robot arm")
    args = parser.parse_args()
    result = args.result_dir.resolve()
    checkpoint = args.checkpoint.resolve()

    observation, sample = build_policy_input(result, args.language)
    env_cfg = make_env_config("libero", task="libero_10", task_ids=[0], observation_height=256,
                              observation_width=256, init_states=True, hard_reset=True,
                              control_mode="relative", max_parallel_tasks=1)
    cfg = PreTrainedConfig.from_pretrained(str(checkpoint))
    cfg.pretrained_path, cfg.device, cfg.dtype, cfg.use_amp = checkpoint, "cuda", "bfloat16", False
    policy = make_policy(cfg=cfg, env_cfg=env_cfg, rename_map={})
    policy.eval()
    pre, post = make_pre_post_processors(
        policy_cfg=cfg, pretrained_path=str(checkpoint),
        preprocessor_overrides={"device_processor": {"device": "cuda"},
                                "rename_observations_processor": {"rename_map": {}}},
    )

    torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats(); torch.cuda.synchronize()
    started = time.perf_counter()
    with torch.inference_mode():
        normalized = policy.predict_action_chunk(pre(copy.deepcopy(observation)))
    torch.cuda.synchronize()
    inference_ms = (time.perf_counter() - started) * 1000.0
    chunk = post(normalized).detach().cpu().numpy()
    if chunk.shape != (1, 50, 7) or not np.isfinite(chunk).all():
        raise RuntimeError(f"无效 action chunk: shape={chunk.shape}, finite={np.isfinite(chunk).all()}")
    np.save(result / "vla_action_raw.npy", chunk[0])
    first = chunk[0, 0].astype(np.float64)

    eef = json.loads((result / "eef_pose.json").read_text(encoding="utf-8"))
    safety = SafetyConfig()
    adapter_started = time.perf_counter()
    adapted = adapt_libero_action(first, np.asarray(eef["position_xyz_m"]),
                                  quat_wxyz_to_matrix(np.asarray(eef["quaternion_wxyz"])), safety)
    adapter_ms = (time.perf_counter() - adapter_started) * 1000.0
    processed = {
        "checkpoint_postprocessor_applied": True,
        "predict_action_chunk_calls": 1,
        "chunk_shape": list(chunk.shape),
        "first_action_index": 0,
        "first_action": first.tolist(),
        "remaining_actions_executed": 0,
        "action_semantics": ["dimensionless OSC input dx", "dimensionless OSC input dy", "dimensionless OSC input dz",
                             "dimensionless world-axis-angle input drx", "dimensionless world-axis-angle input dry",
                             "dimensionless world-axis-angle input drz", "gripper (-1 open, +1 close)"],
    }
    (result / "vla_action_processed.json").write_text(json.dumps(processed, indent=2), encoding="utf-8")
    adapted["safety_config"] = safety.__dict__
    adapted["source_observation_state"] = sample["robot_state_8d"]
    (result / "vla_action_bounded.json").write_text(json.dumps(adapted, indent=2), encoding="utf-8")
    gpu = {
        "inference_latency_ms": inference_ms,
        "adapter_latency_ms": adapter_ms,
        "torch_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        "torch_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
        "nvidia_smi": subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,memory.used",
                                                "--format=csv,noheader,nounits"], text=True).strip(),
        "oom": False,
    }
    (result / "policy_once_metrics.json").write_text(json.dumps(gpu, indent=2), encoding="utf-8")
    print(json.dumps({"inference": "PASS", "calls": 1, "first_action": first.tolist()}), flush=True)


if __name__ == "__main__":
    main()
