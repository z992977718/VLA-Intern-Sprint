#!/usr/bin/env python3
"""Isolate Isaac startup stages on RTX 5090 without policy or robot control."""

from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from pathlib import Path

import numpy as np

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")


def mark(path: Path, label: str, started: float) -> None:
    message = {"event": label, "elapsed_sec": time.monotonic() - started, "wall_time": time.time()}
    print(json.dumps(message), flush=True)
    path.write_text(json.dumps(message, indent=2) + "\n", encoding="utf-8")


def make_camera_scene(app, count: int, started: float, output: Path) -> dict:
    mark(output / "milestone_02_import_core.json", "before_isaac_core_imports", started)
    from isaacsim.core.api import World
    from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera

    mark(output / "milestone_03_core_ready.json", "after_isaac_core_imports", started)
    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()
    positions = [np.array([1.35, 1.35, 1.15], dtype=np.float32), np.array([-1.35, 1.35, 1.15], dtype=np.float32)]
    sensors = []
    for index in range(count):
        camera = RtxCamera(
            path=f"/World/StartupDiagnosticCamera{index}",
            tick_rate=10.0,
            positions=positions[index],
            orientations=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
        )
        sensors.append(CameraSensor(camera, resolution=(256, 256), annotators=["rgb"]))
    mark(output / "milestone_04_cameras_created.json", f"after_{count}_camera_creation", started)
    app.update()
    world.reset()
    world.play()
    for _ in range(30):
        world.step(render=True)
    frames = []
    for sensor in sensors:
        data, _ = sensor.get_data("rgb")
        array = data.numpy()
        frames.append({"shape": list(array.shape), "min": int(array.min()), "max": int(array.max()), "std": float(array.std())})
    mark(output / "milestone_05_frames_read.json", f"after_{count}_camera_frame_read", started)
    return {"camera_count": count, "frames": frames}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("base", "single_camera", "dual_camera", "ros2_only"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True)
    started = time.monotonic()
    app = None
    result = {"mode": args.mode, "pass": False, "ready": False, "policy_loaded": False, "robot_control": False}
    try:
        mark(output / "milestone_00_before_simulation_app.json", "before_SimulationApp", started)
        from isaacsim import SimulationApp

        app = SimulationApp({"headless": True, "renderer": "RaytracedLighting"})
        mark(output / "milestone_01_simulation_app_ready.json", "after_SimulationApp", started)
        if args.mode == "base":
            for _ in range(10):
                app.update()
            mark(output / "milestone_02_base_updates.json", "after_base_updates", started)
            result["details"] = {"updates": 10}
        elif args.mode == "single_camera":
            result["details"] = make_camera_scene(app, 1, started, output)
        elif args.mode == "dual_camera":
            result["details"] = make_camera_scene(app, 2, started, output)
        else:
            mark(output / "milestone_02_before_ros2_enable.json", "before_ros2_bridge_enable", started)
            from isaacsim.core.utils.extensions import enable_extension

            enable_extension("isaacsim.ros2.bridge")
            mark(output / "milestone_03_ros2_enable_called.json", "after_ros2_bridge_enable_call", started)
            for _ in range(20):
                app.update()
            mark(output / "milestone_04_ros2_updates.json", "after_ros2_bridge_updates", started)
            result["details"] = {"extension": "isaacsim.ros2.bridge", "updates": 20}
        result.update({"pass": True, "ready": True, "elapsed_sec": time.monotonic() - started})
    except Exception:
        result.update({"exception": traceback.format_exc(), "elapsed_sec": time.monotonic() - started})
        (output / "exception.txt").write_text(result["exception"], encoding="utf-8")
        raise
    finally:
        if app is not None:
            app.close()
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
