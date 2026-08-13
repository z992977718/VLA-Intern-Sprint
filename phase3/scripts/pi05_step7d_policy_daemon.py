#!/usr/bin/env python3
"""Serve exactly one frozen-checkpoint Pi0.5 diagnostic episode for Step 7D."""

from __future__ import annotations

import argparse
import copy
import json
import time
import traceback
from pathlib import Path

import numpy as np
import torch
from lerobot.configs.policies import PreTrainedConfig
from lerobot.envs.factory import make_env_config
from lerobot.policies.factory import make_policy, make_pre_post_processors

from action_adapter_step4 import SafetyConfig, adapt_libero_action
from phase3_step6_common import LANGUAGE, atomic_json
from policy_input_adapter import build_policy_input
from run_pi05_step4_once import quat_wxyz_to_matrix


def wait_for(path: Path, alternate: Path | None, deadline: float) -> str:
    while time.monotonic() < deadline:
        if path.is_file():
            return "path"
        if alternate is not None and alternate.is_file():
            return "alternate"
        time.sleep(0.02)
    raise TimeoutError(f"timed out waiting for {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--max-cycles", type=int, default=100)
    parser.add_argument("--language", default=LANGUAGE)
    args = parser.parse_args()
    if args.max_cycles != 100 or args.language != LANGUAGE:
        raise ValueError("Step 7D requires state 0, 100 max cycles, and the frozen instruction")

    result = args.result_dir.resolve()
    if (result / "policy_complete.json").exists():
        raise FileExistsError("refusing to overwrite a completed Step 7D policy run")
    env = make_env_config(
        "libero", task="libero_10", task_ids=[0], observation_height=256,
        observation_width=256, init_states=True, hard_reset=True,
        control_mode="relative", max_parallel_tasks=1,
    )
    config = PreTrainedConfig.from_pretrained(str(args.checkpoint))
    config.pretrained_path = args.checkpoint
    config.device = "cuda"
    config.dtype = "bfloat16"
    config.use_amp = False
    load_started = time.perf_counter()
    policy = make_policy(cfg=config, env_cfg=env, rename_map={})
    policy.eval()
    preprocessor, postprocessor = make_pre_post_processors(
        policy_cfg=config,
        pretrained_path=str(args.checkpoint),
        preprocessor_overrides={
            "device_processor": {"device": "cuda"},
            "rename_observations_processor": {"rename_map": {}},
        },
    )
    torch.cuda.synchronize()
    atomic_json(
        result / "policy_ready.json",
        {
            "ready": True,
            "checkpoint": str(args.checkpoint.resolve()),
            "model_load_sec": time.perf_counter() - load_started,
            "episodes": 1,
            "initial_state_id": 0,
            "diagnostic_not_counted": True,
            "max_cycles": 100,
            "language": LANGUAGE,
            "precision": "bfloat16",
            "policy_mode": "eval/inference",
            "training_or_weight_update": False,
        },
    )
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    safety = SafetyConfig(
        translation_action_limit=0.10,
        rotation_action_limit=0.05,
        max_joint_step_rad=0.05,
        workspace_min_xyz_m=(-0.35, -0.55, 0.40),
        workspace_max_xyz_m=(0.30, 0.70, 1.05),
    )
    records: list[dict] = []
    try:
        for cycle_index in range(100):
            cycle = result / f"cycle_{cycle_index:03d}"
            status = wait_for(
                cycle / "observation_ready.json",
                result / "episode_complete.json",
                time.monotonic() + 180.0,
            )
            if status == "alternate":
                break
            metadata = json.loads((cycle / "observation_ready.json").read_text(encoding="utf-8"))
            observation, sample = build_policy_input(cycle, LANGUAGE)
            atomic_json(cycle / "policy_input_sample.json", sample)
            torch.cuda.synchronize()
            started = time.perf_counter()
            with torch.inference_mode():
                normalized_chunk = policy.predict_action_chunk(preprocessor(copy.deepcopy(observation)))
            torch.cuda.synchronize()
            inference_ms = (time.perf_counter() - started) * 1000.0
            chunk = postprocessor(normalized_chunk).detach().cpu().numpy()
            if chunk.shape != (1, 50, 7) or not np.isfinite(chunk).all():
                raise RuntimeError(f"invalid action chunk {chunk.shape}")
            np.save(cycle / "action_chunk.npy", chunk[0])
            first = chunk[0, 0].astype(np.float64)
            eef = json.loads((cycle / "eef_pose.json").read_text(encoding="utf-8"))
            adapter_started = time.perf_counter()
            bounded = adapt_libero_action(
                first,
                np.asarray(eef["position_xyz_m"], dtype=np.float64),
                quat_wxyz_to_matrix(np.asarray(eef["quaternion_wxyz"], dtype=np.float64)),
                safety,
            )
            adapter_ms = (time.perf_counter() - adapter_started) * 1000.0
            response = {
                "episode_index": 0,
                "cycle_index": cycle_index,
                "initial_state_id": 0,
                "diagnostic_not_counted": True,
                "observation_timestamp": metadata["observation_timestamp"],
                "predict_action_chunk_calls_this_cycle": 1,
                "chunk_shape": list(chunk.shape),
                "chunk_finite": True,
                "raw_first_action": first.tolist(),
                "bounded": bounded,
                "inference_latency_ms": inference_ms,
                "adapter_latency_ms": adapter_ms,
                "action_index_authorized": 0,
                "remaining_49_actions_authorized": False,
                "torch_allocated_bytes": torch.cuda.memory_allocated(),
                "torch_reserved_bytes": torch.cuda.memory_reserved(),
            }
            atomic_json(cycle / "policy_response.json", response)
            records.append(response)
            wait_for(
                cycle / "execution_complete.json",
                result / "episode_complete.json",
                time.monotonic() + 180.0,
            )
            if (result / "episode_complete.json").is_file():
                break
        # Isaac writes execution_complete first and episode_complete immediately
        # afterwards on the final cycle. Give that final file hand-off a bounded
        # grace period instead of treating the sub-second ordering as failure.
        if not (result / "episode_complete.json").is_file():
            wait_for(result / "episode_complete.json", None, time.monotonic() + 5.0)
        atomic_json(
            result / "policy_complete.json",
            {
                "completed": True,
                "episodes": 1,
                "initial_state_id": 0,
                "diagnostic_not_counted": True,
                "total_real_inference_calls": len(records),
                "inference_latency_ms": [row["inference_latency_ms"] for row in records],
                "torch_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                "torch_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
                "oom": False,
                "training_or_weight_update": False,
            },
        )
    except Exception:
        atomic_json(
            result / "policy_complete.json",
            {
                "completed": False,
                "episodes": 1,
                "initial_state_id": 0,
                "diagnostic_not_counted": True,
                "total_real_inference_calls": len(records),
                "torch_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                "torch_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
                "oom": "out of memory" in traceback.format_exc().lower(),
                "training_or_weight_update": False,
                "exception": traceback.format_exc(),
            },
        )
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
