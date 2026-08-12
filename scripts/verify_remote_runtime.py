#!/usr/bin/env python3
"""Print the remote VLA runtime versions and assert CUDA availability."""

from __future__ import annotations

import importlib.metadata
import sys

import libero
import lerobot
import torch
import torchcodec
import torchvision


print("python:", sys.version)
print("torch:", torch.__version__)
print("torchvision:", torchvision.__version__)
print("torchcodec:", importlib.metadata.version("torchcodec"))
print("lerobot:", lerobot.__version__)
print("libero:", libero.__file__)
print("numpy:", importlib.metadata.version("numpy"))
print("torch_cuda:", torch.version.cuda)
print("cuda_available:", torch.cuda.is_available())
print("bf16_supported:", torch.cuda.is_bf16_supported() if torch.cuda.is_available() else False)
print("gpu:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)

assert torch.cuda.is_available(), "CUDA is not available"
