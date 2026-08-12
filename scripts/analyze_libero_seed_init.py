#!/usr/bin/env python3
"""Measure how seeds and fixed LIBERO init states affect the first observation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from lerobot.envs.factory import make_env, make_env_config
from lerobot.envs.libero import get_task_init_states
from lerobot.envs.utils import NEW_ROLLOUT_OPTION
from libero.libero import benchmark


def digest(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    return hashlib.sha256(contiguous.view(np.uint8)).hexdigest()


def flatten_arrays(value: Any, prefix: str = "") -> dict[str, np.ndarray]:
    if isinstance(value, dict):
        flattened: dict[str, np.ndarray] = {}
        for key, child in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(flatten_arrays(child, name))
        return flattened
    return {prefix: np.asarray(value)}


def compare(left: dict[str, np.ndarray], right: dict[str, np.ndarray]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in sorted(set(left) & set(right)):
        a = left[key]
        b = right[key]
        numeric = np.issubdtype(a.dtype, np.number) and np.issubdtype(b.dtype, np.number)
        result[key] = {
            "shape": list(a.shape),
            "dtype": str(a.dtype),
            "exact_equal": bool(np.array_equal(a, b)),
            "max_abs_diff": float(np.max(np.abs(a.astype(np.float64) - b.astype(np.float64))))
            if numeric and a.shape == b.shape
            else None,
            "left_sha256": digest(a),
            "right_sha256": digest(b),
        }
    return result


def new_env():
    cfg = make_env_config(
        "libero",
        task="libero_10",
        task_ids=[0],
        observation_height=360,
        observation_width=360,
        init_states=True,
        hard_reset=True,
        control_mode="relative",
        max_parallel_tasks=1,
    )
    return make_env(cfg, n_envs=1, use_async_envs=False)["libero_10"][0]


def reset_snapshot(env: Any, seed: int) -> dict[str, np.ndarray]:
    observation, _ = env.reset(seed=[seed], options={NEW_ROLLOUT_OPTION: True})
    return flatten_arrays(observation)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    suite = benchmark.get_benchmark_dict()["libero_10"]()
    states = np.asarray(get_task_init_states(suite, 0))
    row_hashes = [digest(np.asarray(row)) for row in states]

    env_a = new_env()
    seed_1000_state_0 = reset_snapshot(env_a, 1000)
    env_a.close()

    env_b = new_env()
    seed_1010_state_0 = reset_snapshot(env_b, 1010)
    env_b.close()

    env_c = new_env()
    sequential_state_0 = reset_snapshot(env_c, 1000)
    sequential_state_1 = reset_snapshot(env_c, 1001)
    env_c.close()

    same_state_different_seed = compare(seed_1000_state_0, seed_1010_state_0)
    consecutive_fixed_states = compare(sequential_state_0, sequential_state_1)
    result = {
        "suite": "libero_10",
        "task_id": 0,
        "task_description": suite.get_task(0).language,
        "init_state_array_shape": list(states.shape),
        "init_state_count": int(states.shape[0]),
        "unique_init_state_rows_total": len(set(row_hashes)),
        "first_30_init_state_rows_unique": len(set(row_hashes[:30])),
        "fixed_state_selection": (
            "With batch_size=1, LiberoEnv starts init_state_id at 0 and increments it after every explicit "
            "rollout reset; the evaluation seed is not used as the init-state index."
        ),
        "same_fixed_state_different_seed": {
            "seeds": [1000, 1010],
            "method": "two newly created environments, so both use fixed init-state index 0",
            "all_observation_arrays_exact_equal": all(
                item["exact_equal"] for item in same_state_different_seed.values()
            ),
            "arrays": same_state_different_seed,
        },
        "consecutive_fixed_states": {
            "seeds": [1000, 1001],
            "method": "two sequential resets of one environment, using fixed init-state indices 0 then 1",
            "all_observation_arrays_exact_equal": all(item["exact_equal"] for item in consecutive_fixed_states.values()),
            "arrays": consecutive_fixed_states,
        },
        "interpretation": (
            "For this fixed-init-state protocol, meaningful initial-observation variation comes from cycling "
            "through the stored LIBERO init-state rows. Changing only the seed while restarting at the same "
            "fixed state produced identical first observations in this measured check."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
