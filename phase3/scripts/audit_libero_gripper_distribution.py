#!/usr/bin/env python3
"""Read-only gripper distribution audit for cached lerobot/libero data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    values = []
    parquet_files = sorted((args.root / "data").glob("chunk-*/*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No cached parquet files under {args.root}")
    for file in parquet_files:
        table = pq.read_table(file, columns=["observation.state"])
        column = table.column("observation.state").to_pylist()
        values.extend(np.asarray(row[6:8], dtype=np.float64) for row in column)
    values = np.asarray(values)
    q0, q1 = values[:, 0], values[:, 1]
    payload = {
        "dataset": "lerobot/libero", "revision": args.revision, "cache_root": str(args.root), "frames_scanned": int(len(values)),
        "state_dimensions": [6, 7],
        "per_dimension": [
            {"index": 6, "min": float(q0.min()), "max": float(q0.max()), "mean": float(q0.mean())},
            {"index": 7, "min": float(q1.min()), "max": float(q1.max()), "mean": float(q1.mean())},
        ],
        "sum_abs_max": float(np.abs(q0 + q1).max()),
        "sum_abs_mean": float(np.abs(q0 + q1).mean()),
        "opposite_sign_fraction": float(np.mean(np.sign(q0) == -np.sign(q1))),
        "interpretation": "These are the two gripper values after the recorded LeRobot LIBERO processing path. They establish the data distribution used by Pi0.5 input normalization.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
