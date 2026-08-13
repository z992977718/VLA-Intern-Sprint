#!/usr/bin/env python3
"""Read Isaac Panda frame definitions only; no policy or task control."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")

from isaacsim import SimulationApp

from isaac_step6_scene_gate import build_scene, prim_world_pose


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")

    app = SimulationApp({"headless": True, "renderer": "RaytracedLighting"})
    try:
        scene = build_scene(app, 0, dynamic_objects=False)
        stage = scene["stage"]
        records = []
        for prim in stage.Traverse():
            path = str(prim.GetPath())
            name = prim.GetName().lower()
            if "panda" not in path.lower() or not any(token in name for token in ("hand", "grip", "eef", "tool", "finger")):
                continue
            position, quaternion = prim_world_pose(stage, scene["Usd"], scene["UsdGeom"], path)
            records.append({
                "path": path,
                "name": prim.GetName(),
                "parent": str(prim.GetParent().GetPath()),
                "type": str(prim.GetTypeName()),
                "world_position_xyz_m": position.tolist(),
                "world_quaternion_wxyz": quaternion.tolist(),
            })
        payload = {
            "scope": "frame-tree inspection only; no Pi0.5, no task action, no rollout",
            "robot_dof_names": list(scene["robot"].dof_names),
            "candidate_frames": records,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
