#!/usr/bin/env python3
"""Initialize, reset, inspect, and close one LIBERO environment."""

from __future__ import annotations

import torch

from lerobot.envs.factory import make_env, make_env_config


print("LIBERO_CONFIG_START", flush=True)
cfg = make_env_config(
    "libero",
    task="libero_10",
    task_ids=[0],
    observation_height=64,
    observation_width=64,
)
print("LIBERO_CONFIG_OK", flush=True)
print("LIBERO_MAKE_ENV_START", flush=True)
envs = make_env(cfg, n_envs=1)
print("LIBERO_MAKE_ENV_OK", flush=True)
env = envs["libero_10"][0]
try:
    print("LIBERO_RESET_START", flush=True)
    obs, _ = env.reset()
    print("LIBERO_RESET_OK", flush=True)
    print("observation_keys:", sorted(obs.keys()), flush=True)
    print("action_space:", env.action_space, flush=True)
    print("action_shape:", env.action_space.shape, flush=True)
    print("cuda_available:", torch.cuda.is_available(), flush=True)
finally:
    env.close()
    print("LIBERO_CLOSE_OK", flush=True)
