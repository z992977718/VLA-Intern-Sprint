#!/usr/bin/env python3
"""Run exactly three real pi0.5 action-chunk inferences without executing actions."""

from __future__ import annotations

import argparse
import copy
import json
import os
import platform
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image

from lerobot.configs.policies import PreTrainedConfig
from lerobot.envs.factory import make_env_config
from lerobot.policies.factory import make_policy, make_pre_post_processors

from policy_input_adapter import build_policy_input


def tensor_schema(value: Any) -> dict[str, Any]:
    if isinstance(value, torch.Tensor):
        return {
            "type": "torch.Tensor",
            "shape": list(value.shape),
            "dtype": str(value.dtype),
            "device": str(value.device),
            "finite": bool(torch.isfinite(value).all().item()) if value.is_floating_point() else None,
        }
    if isinstance(value, list):
        return {"type": "list", "length": len(value), "item_type": type(value[0]).__name__ if value else None}
    return {"type": type(value).__name__}


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), q))


def save_policy_input_image(tensor: torch.Tensor, path: Path) -> None:
    image = tensor[0].detach().cpu().clamp(0, 1).permute(1, 2, 0).numpy()
    Image.fromarray(np.rint(image * 255).astype(np.uint8), mode="RGB").save(path)


def nvidia_smi() -> str:
    command = [
        "nvidia-smi",
        "--query-gpu=timestamp,name,driver_version,memory.total,memory.used,memory.free,utilization.gpu",
        "--format=csv,noheader,nounits",
    ]
    return subprocess.check_output(command, text=True).strip()


def optional_git_commit(path: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--language", default="move the robot arm")
    args = parser.parse_args()

    result_dir = args.result_dir.resolve()
    checkpoint = args.checkpoint.resolve()
    result_dir.mkdir(parents=True, exist_ok=True)
    if not (checkpoint / "model.safetensors").is_file():
        raise FileNotFoundError(f"Missing checkpoint model.safetensors: {checkpoint}")

    observation, robot_state_sample = build_policy_input(result_dir, args.language)
    (result_dir / "robot_state_sample.json").write_text(
        json.dumps(robot_state_sample, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    save_policy_input_image(observation["observation.images.image"], result_dir / "policy_input_external.png")
    save_policy_input_image(observation["observation.images.image2"], result_dir / "policy_input_wrist.png")

    env_cfg = make_env_config(
        "libero",
        task="libero_10",
        task_ids=[0],
        observation_height=256,
        observation_width=256,
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

    config_evidence = {
        "checkpoint_path": str(checkpoint),
        "policy_type": policy_cfg.type,
        "device": policy_cfg.device,
        "dtype": policy_cfg.dtype,
        "use_amp": policy_cfg.use_amp,
        "chunk_size": policy_cfg.chunk_size,
        "n_action_steps": policy_cfg.n_action_steps,
        "num_inference_steps": policy_cfg.num_inference_steps,
        "input_features": {key: {"type": str(value.type), "shape": list(value.shape)} for key, value in policy_cfg.input_features.items()},
        "output_features": {key: {"type": str(value.type), "shape": list(value.shape)} for key, value in policy_cfg.output_features.items()},
        "gradient_checkpointing": policy_cfg.gradient_checkpointing,
        "train_expert_only": policy_cfg.train_expert_only,
        "freeze_vision_encoder": policy_cfg.freeze_vision_encoder,
        "processor_config": str(checkpoint / "policy_preprocessor.json"),
        "postprocessor_config": str(checkpoint / "policy_postprocessor.json"),
        "inference_only": True,
        "optimizer_created": False,
        "backward_executed": False,
        "action_execution_code_present": False,
    }
    (result_dir / "checkpoint_config.json").write_text(
        json.dumps(config_evidence, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    load_started = time.perf_counter()
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
    torch.cuda.synchronize()
    model_load_sec = time.perf_counter() - load_started

    preprocessed = preprocessor(copy.deepcopy(observation))
    input_schema = {
        "adapter_output_before_checkpoint_processor": {
            key: tensor_schema(value) for key, value in observation.items()
        },
        "model_input_after_checkpoint_processor": {
            key: tensor_schema(value) for key, value in preprocessed.items()
        },
        "image_mapping": {
            "external_camera": "observation.images.image",
            "wrist_follow_camera": "observation.images.image2",
            "semantic_compatibility": "PARTIAL",
            "reason": "the second view follows panda_hand but is not a calibrated rigid eye-in-hand camera",
        },
        "state_mapping": {
            "source": "named /joint_states + Isaac panda_hand /World transform",
            "target": "observation.state [EEF xyz, EEF axis-angle, two gripper qpos]",
            "processor": "lerobot.processor.env_processor.LiberoProcessorStep",
            "semantic_compatibility": "PARTIAL",
        },
        "language": args.language,
    }
    (result_dir / "input_schema.json").write_text(
        json.dumps(input_schema, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    latencies_ms: list[float] = []
    chunks: list[np.ndarray] = []
    records: list[dict[str, Any]] = []
    oom = False
    try:
        for call_index in range(3):
            model_input = preprocessor(copy.deepcopy(observation))
            torch.cuda.synchronize()
            started = time.perf_counter()
            with torch.inference_mode():
                normalized_chunk = policy.predict_action_chunk(model_input)
            torch.cuda.synchronize()
            latency_ms = (time.perf_counter() - started) * 1000.0
            action_chunk = postprocessor(normalized_chunk).detach().cpu()
            array = action_chunk.numpy()
            latencies_ms.append(latency_ms)
            chunks.append(array)
            records.append(
                {
                    "call_index": call_index,
                    "latency_ms": latency_ms,
                    "shape": list(array.shape),
                    "dtype": str(array.dtype),
                    "finite": bool(np.isfinite(array).all()),
                    "min": float(array.min()),
                    "max": float(array.max()),
                    "mean": float(array.mean()),
                    "first_action": array[0, 0].tolist(),
                    "last_action": array[0, -1].tolist(),
                }
            )
    except torch.cuda.OutOfMemoryError:
        oom = True
        raise

    all_chunks = np.concatenate(chunks, axis=0)
    np.save(result_dir / "action_chunk.npy", chunks[0][0])
    np.save(result_dir / "action_chunks_3_calls.npy", all_chunks)
    action_summary = {
        "postprocessed_with_checkpoint_unnormalizer": True,
        "executed_on_robot": False,
        "published_to_ros": False,
        "calls": records,
        "all_calls_finite": bool(np.isfinite(all_chunks).all()),
        "observed_shape_per_call": records[0]["shape"],
        "saved_action_chunk_shape": list(chunks[0][0].shape),
    }
    (result_dir / "action_chunk_summary.json").write_text(
        json.dumps(action_summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    latency = {
        "measurement": "torch.cuda.synchronize immediately before and after each predict_action_chunk call",
        "cached_action_used": False,
        "number_of_real_calls": len(latencies_ms),
        "latency_ms": latencies_ms,
        "mean_ms": statistics.fmean(latencies_ms),
        "median_ms": statistics.median(latencies_ms),
        "p95_ms": percentile(latencies_ms, 95),
        "model_load_sec": model_load_sec,
    }
    (result_dir / "inference_latency.json").write_text(
        json.dumps(latency, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    cuda_memory = {
        "device_name": torch.cuda.get_device_name(0),
        "device_total_bytes": torch.cuda.get_device_properties(0).total_memory,
        "torch_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        "torch_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
        "nvidia_smi_after_inference": nvidia_smi(),
        "oom": oom,
    }
    (result_dir / "gpu_memory.txt").write_text(
        json.dumps(cuda_memory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    environment = {
        "timestamp": time.time(),
        "hostname": platform.node(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0),
        "checkpoint": str(checkpoint),
        "project_git_commit": optional_git_commit(Path.cwd()),
        "lerobot_git_commit": optional_git_commit(Path.cwd() / "lerobot"),
    }
    (result_dir / "environment.txt").write_text(
        json.dumps(environment, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    status = {
        "policy_input_adapter": "PASS",
        "checkpoint_loaded": "PASS",
        "real_predict_action_chunk_calls": len(records),
        "action_chunk_shape_valid": all(record["shape"] == [1, 50, 7] for record in records),
        "all_actions_finite": action_summary["all_calls_finite"],
        "oom": oom,
        "action_published": False,
        "action_executed": False,
        "inference": "PASS" if len(records) == 3 and action_summary["all_calls_finite"] else "FAIL",
    }
    (result_dir / "policy_run_status.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(status, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
