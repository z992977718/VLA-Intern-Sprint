#!/usr/bin/env python3
"""Offline preflight for the migrated Pi0.5 model, tokenizer, and LIBERO dataset."""

from __future__ import annotations

import math
from pathlib import Path

from lerobot.datasets.lerobot_dataset import LeRobotDataset
from safetensors import safe_open
from transformers import AutoTokenizer


model_dir = Path("/root/autodl-tmp/cache/huggingface/pi05_libero_base")
dataset_dir = Path("/root/autodl-tmp/cache/huggingface/lerobot/lerobot/libero")
model_file = model_dir / "model.safetensors"

print("PI05_MODEL_START", flush=True)
with safe_open(model_file, framework="pt", device="cpu") as weights:
    tensor_count = len(weights.keys())
print("model_safetensors_bytes:", model_file.stat().st_size, flush=True)
print("model_tensor_count:", tensor_count, flush=True)

print("PI05_TOKENIZER_START", flush=True)
tokenizer = AutoTokenizer.from_pretrained("google/paligemma-3b-pt-224", local_files_only=True)
print("tokenizer_class:", type(tokenizer).__name__, flush=True)
print("tokenizer_vocab_size:", len(tokenizer), flush=True)

print("PI05_DATASET_START", flush=True)
dataset = LeRobotDataset(
    "lerobot/libero",
    root=dataset_dir,
    revision="a1aaacb7f6cd6ee5fb43120f673cebb0cfea7dd4",
    video_backend="torchcodec",
    return_uint8=True,
)
sample = dataset[0]
print("dataset_frames:", dataset.num_frames, flush=True)
print("dataset_episodes:", dataset.num_episodes, flush=True)
print("camera_keys:", dataset.meta.camera_keys, flush=True)
for key in dataset.meta.camera_keys:
    value = sample[key]
    print(f"{key}: shape={tuple(value.shape)} dtype={value.dtype}", flush=True)
print("observation.state:", tuple(sample["observation.state"].shape), flush=True)
print("action:", tuple(sample["action"].shape), flush=True)
print("sample_action_finite:", all(math.isfinite(float(x)) for x in sample["action"]), flush=True)
print("PI05_ASSET_PREFLIGHT_OK", flush=True)
