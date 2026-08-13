#!/usr/bin/env python3
"""Inspect source OBJ bounds for the four LIBERO assets reused by Step 6."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


ASSETS = {
    "alphabet_soup": ("stable_hope_objects/alphabet_soup/textured.obj", 0.01),
    "tomato_sauce": ("stable_hope_objects/tomato_sauce/textured.obj", 0.01),
    "basket": ("stable_scanned_objects/basket/basket.obj", 1.0),
    "living_room_table": ("scenes/living_room_table/living_room_table.obj", 1.5),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def obj_vertices(path: Path) -> np.ndarray:
    vertices = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("v "):
                values = line.split()
                vertices.append([float(values[1]), float(values[2]), float(values[3])])
    array = np.asarray(vertices, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise RuntimeError(f"No OBJ vertices in {path}")
    return array


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {}
    for name, (relative, scale) in ASSETS.items():
        path = args.asset_root / relative
        vertices = obj_vertices(path) * scale
        minimum = vertices.min(axis=0)
        maximum = vertices.max(axis=0)
        result[name] = {
            "path": str(path.resolve()),
            "sha256": sha256(path),
            "mujoco_visual_scale": [scale, scale, scale],
            "vertex_count": int(len(vertices)),
            "scaled_min_xyz_m": minimum.tolist(),
            "scaled_max_xyz_m": maximum.tolist(),
            "scaled_dimensions_xyz_m": (maximum - minimum).tolist(),
            "scaled_center_xyz_m": ((minimum + maximum) / 2).tolist(),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
