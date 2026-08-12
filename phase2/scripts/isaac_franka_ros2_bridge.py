#!/usr/bin/env python3
"""启动 headless Isaac Sim、官方 Franka 资产和 ROS 2 关节闭环图。"""

from __future__ import annotations

import json
import os
import time
import traceback
from pathlib import Path

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")

from isaacsim import SimulationApp


RESULT_DIR = Path("/root/autodl-tmp/VLA-Intern-Sprint/results/phase2_step1")
READY_FILE = RESULT_DIR / "isaac_ready.json"
STOP_FILE = RESULT_DIR / "stop_isaac"


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    READY_FILE.unlink(missing_ok=True)
    STOP_FILE.unlink(missing_ok=True)

    app = SimulationApp(
        {
            "headless": True,
            "renderer": "RaytracedLighting",
            "width": 1280,
            "height": 720,
        }
    )

    try:
        import omni.graph.core as og
        import omni.kit.app
        from isaacsim.core.api import World
        from isaacsim.core.utils.extensions import enable_extension
        from isaacsim.core.utils.stage import add_reference_to_stage
        from isaacsim.storage.native import get_assets_root_path
        from pxr import UsdGeom

        enable_extension("isaacsim.ros2.bridge")
        for _ in range(10):
            app.update()

        assets_root = get_assets_root_path()
        if not assets_root:
            raise RuntimeError("无法解析 Isaac Sim 官方在线 assets root")
        franka_asset = f"{assets_root}/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd"

        world = World(stage_units_in_meters=1.0)
        world.scene.add_default_ground_plane()
        add_reference_to_stage(usd_path=franka_asset, prim_path="/panda")
        for _ in range(30):
            app.update()

        prim = world.stage.GetPrimAtPath("/panda")
        if not prim or not prim.IsValid():
            raise RuntimeError(f"Franka USD 加载失败: {franka_asset}")

        world.reset()
        og.Controller.edit(
            {"graph_path": "/ActionGraph", "evaluator_name": "execution"},
            {
                og.Controller.Keys.CREATE_NODES: [
                    ("OnPlaybackTick", "omni.graph.action.OnPlaybackTick"),
                    ("PublishJointState", "isaacsim.ros2.bridge.ROS2PublishJointState"),
                    ("SubscribeJointState", "isaacsim.ros2.bridge.ROS2SubscribeJointState"),
                    ("ArticulationController", "isaacsim.core.nodes.IsaacArticulationController"),
                    ("ReadSimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
                ],
                og.Controller.Keys.CONNECT: [
                    ("OnPlaybackTick.outputs:tick", "PublishJointState.inputs:execIn"),
                    ("OnPlaybackTick.outputs:tick", "SubscribeJointState.inputs:execIn"),
                    ("OnPlaybackTick.outputs:tick", "ArticulationController.inputs:execIn"),
                    ("ReadSimTime.outputs:simulationTime", "PublishJointState.inputs:timeStamp"),
                    ("SubscribeJointState.outputs:jointNames", "ArticulationController.inputs:jointNames"),
                    ("SubscribeJointState.outputs:positionCommand", "ArticulationController.inputs:positionCommand"),
                    ("SubscribeJointState.outputs:velocityCommand", "ArticulationController.inputs:velocityCommand"),
                    ("SubscribeJointState.outputs:effortCommand", "ArticulationController.inputs:effortCommand"),
                ],
                og.Controller.Keys.SET_VALUES: [
                    ("ArticulationController.inputs:robotPath", "/panda"),
                    ("PublishJointState.inputs:targetPrim", "/panda"),
                ],
            },
        )

        world.play()
        for _ in range(60):
            world.step(render=True)

        READY_FILE.write_text(
            json.dumps(
                {
                    "timestamp": time.time(),
                    "isaac_version": omni.kit.app.get_app().get_app_version(),
                    "renderer": "RaytracedLighting",
                    "headless": True,
                    "franka_asset": franka_asset,
                    "franka_prim": str(prim.GetPath()),
                    "stage_up_axis": str(UsdGeom.GetStageUpAxis(world.stage)),
                    "ros2_bridge_extension": "isaacsim.ros2.bridge",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"ISAAC_READY={READY_FILE}", flush=True)

        deadline = time.monotonic() + 180
        while app.is_running() and time.monotonic() < deadline and not STOP_FILE.exists():
            world.step(render=True)

        print("ISAAC_STOPPING", flush=True)
    except Exception:
        (RESULT_DIR / "isaac_exception.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        app.close()


if __name__ == "__main__":
    main()
