#!/usr/bin/env python3
"""Isaac Sim 6.0.1：官方 Franka、两路 RTX RGB camera 与 ROS 2 publisher。"""

from __future__ import annotations

import json
import math
import os
import time
import traceback
from pathlib import Path

import numpy as np

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")

from isaacsim import SimulationApp


RESULT_DIR = Path(
    os.environ.get(
        "PHASE2_RESULT_DIR",
        "/root/autodl-tmp/VLA-Intern-Sprint/results/phase2_step2",
    )
)
READY_FILE = RESULT_DIR / "isaac_ready.json"
STOP_FILE = RESULT_DIR / "stop_isaac"
RESOLUTION = (256, 256)
TICK_RATE_HZ = 10.0
RUNTIME_TIMEOUT_SEC = float(os.environ.get("PHASE2_ISAAC_TIMEOUT_SEC", "180"))


def quaternion_from_rotation_matrix(matrix: np.ndarray) -> np.ndarray:
    """把 3x3 旋转矩阵转换为 scalar-first quaternion (w, x, y, z)。"""
    trace = float(np.trace(matrix))
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        return np.array([0.25 * s, (matrix[2, 1] - matrix[1, 2]) / s,
                         (matrix[0, 2] - matrix[2, 0]) / s, (matrix[1, 0] - matrix[0, 1]) / s])
    index = int(np.argmax(np.diag(matrix)))
    if index == 0:
        s = math.sqrt(1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2]) * 2.0
        return np.array([(matrix[2, 1] - matrix[1, 2]) / s, 0.25 * s,
                         (matrix[0, 1] + matrix[1, 0]) / s, (matrix[0, 2] + matrix[2, 0]) / s])
    if index == 1:
        s = math.sqrt(1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2]) * 2.0
        return np.array([(matrix[0, 2] - matrix[2, 0]) / s, (matrix[0, 1] + matrix[1, 0]) / s,
                         0.25 * s, (matrix[1, 2] + matrix[2, 1]) / s])
    s = math.sqrt(1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1]) * 2.0
    return np.array([(matrix[1, 0] - matrix[0, 1]) / s, (matrix[0, 2] + matrix[2, 0]) / s,
                     (matrix[1, 2] + matrix[2, 1]) / s, 0.25 * s])


def look_at_quaternion(position: np.ndarray, target: np.ndarray) -> np.ndarray:
    """USD Camera 本地 -Z 为前方、本地 +Y 为上方。"""
    forward = target - position
    forward /= np.linalg.norm(forward)
    world_up = np.array([0.0, 0.0, 1.0])
    right = np.cross(forward, world_up)
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    rotation = np.column_stack((right, up, -forward))
    return quaternion_from_rotation_matrix(rotation)


def find_prim_path_by_name(stage, name: str) -> str:
    for prim in stage.Traverse():
        if prim.GetName() == name:
            return str(prim.GetPath())
    raise RuntimeError(f"找不到 prim: {name}")


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    READY_FILE.unlink(missing_ok=True)
    STOP_FILE.unlink(missing_ok=True)
    app = SimulationApp({"headless": True, "renderer": "RaytracedLighting", "width": 1280, "height": 720})

    try:
        import omni.graph.core as og
        import omni.kit.app
        import omni.replicator.core as rep
        import omni.syntheticdata._syntheticdata as sd
        from pxr import Usd, UsdGeom
        import isaacsim.core.experimental.utils.transform as transform_utils
        from isaacsim.core.api import World
        from isaacsim.core.utils.extensions import enable_extension
        from isaacsim.core.utils.stage import add_reference_to_stage
        from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera
        from isaacsim.storage.native import get_assets_root_path

        enable_extension("isaacsim.ros2.bridge")
        for _ in range(10):
            app.update()

        assets_root = get_assets_root_path()
        if not assets_root:
            raise RuntimeError("无法解析 Isaac Sim 官方 assets root")
        franka_asset = f"{assets_root}/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd"

        world = World(stage_units_in_meters=1.0)
        world.scene.add_default_ground_plane()
        add_reference_to_stage(usd_path=franka_asset, prim_path="/panda")
        for _ in range(30):
            app.update()
        world.reset()

        hand_path = find_prim_path_by_name(world.stage, "panda_hand")
        external_position = np.array([1.35, 1.35, 1.15])
        external_camera = RtxCamera(
            path="/World/ExternalCamera",
            tick_rate=TICK_RATE_HZ,
            positions=external_position,
            orientations=look_at_quaternion(external_position, np.array([0.0, 0.0, 0.45])),
        )
        hand_prim = world.stage.GetPrimAtPath(hand_path)
        def get_hand_world_pose() -> tuple[np.ndarray, np.ndarray]:
            """Return panda_hand position and normalized quaternion in USD world coordinates."""
            hand_world_transform = UsdGeom.Xformable(hand_prim).ComputeLocalToWorldTransform(
                Usd.TimeCode.Default()
            )
            position = np.array(hand_world_transform.ExtractTranslation(), dtype=float)
            rotation_quat = hand_world_transform.ExtractRotationQuat()
            imaginary = rotation_quat.GetImaginary()
            quaternion_wxyz = np.array(
                [
                    float(rotation_quat.GetReal()),
                    float(imaginary[0]),
                    float(imaginary[1]),
                    float(imaginary[2]),
                ],
                dtype=float,
            )
            norm = float(np.linalg.norm(quaternion_wxyz))
            if not math.isfinite(norm) or norm <= 1e-12:
                raise RuntimeError(f"Invalid panda_hand quaternion norm: {norm}")
            return position, quaternion_wxyz / norm

        def get_wrist_tracking_pose() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
            hand_position, _ = get_hand_world_pose()
            camera_position = hand_position + np.array([-0.45, -0.65, 0.45])
            camera_target = hand_position + np.array([0.30, 0.0, -0.50])
            camera_orientation = transform_utils.look_at_quaternion(
                eye=camera_position.astype(np.float32),
                target=camera_target.astype(np.float32),
                device="cpu",
            ).numpy()
            return hand_position, camera_position, camera_target, camera_orientation

        hand_world_position, wrist_position, wrist_target, wrist_orientation = get_wrist_tracking_pose()
        wrist_camera = RtxCamera(
            path="/World/WristTrackingCamera",
            tick_rate=TICK_RATE_HZ,
            positions=wrist_position,
            orientations=wrist_orientation,
        )
        app.update()

        camera_specs = [
            (
                "external",
                external_camera,
                "/phase2/external_camera/rgb",
                "external_camera_frame",
                {
                    "reference_frame": "world",
                    "position_xyz_m": external_position.tolist(),
                    "look_at_xyz_m": [0.0, 0.0, 0.45],
                    "orientation_wxyz": look_at_quaternion(
                        external_position, np.array([0.0, 0.0, 0.45])
                    ).tolist(),
                },
            ),
            (
                "wrist",
                wrist_camera,
                "/phase2/wrist_camera/rgb",
                "wrist_camera_frame",
                {
                    "tracking_prim": hand_path,
                    "camera_parent": "/World",
                    "tracking_mode": "world-space camera follows hand position and looks at workspace target",
                    "hand_position_xyz_m": hand_world_position.tolist(),
                    "position_xyz_m": wrist_position.tolist(),
                    "look_at_xyz_m": wrist_target.tolist(),
                    "orientation_wxyz": wrist_orientation.tolist(),
                    "camera_axes": "USD Camera: local -Z forward, local +Y up",
                    "limitation": "virtual tracking view; not a calibrated rigid wrist sensor extrinsic",
                },
            ),
        ]
        sensors = []
        writers = []
        metadata = []
        render_var = omni.syntheticdata.SyntheticData.convert_sensor_type_to_rendervar(sd.SensorType.Rgb.name)
        for label, camera, topic, frame_id, pose in camera_specs:
            sensor = CameraSensor(camera, resolution=RESOLUTION, annotators=["rgb"])
            render_product = str(sensor.render_product.GetPath())
            writer = rep.writers.get(render_var + "ROS2PublishImage")
            writer.initialize(frameId=frame_id, nodeNamespace="", queueSize=1, topicName=topic)
            writer.attach([render_product])
            sensors.append(sensor)
            writers.append(writer)
            metadata.append(
                {
                    "label": label,
                    "prim_path": camera.paths[0],
                    "render_product_path": render_product,
                    "topic": topic,
                    "frame_id": frame_id,
                    "resolution_width_height": list(RESOLUTION),
                    "tick_rate_hz": TICK_RATE_HZ,
                    "configured_pose": pose,
                    "visual_pose_validation": "pending until a real RGB frame is rendered",
                }
            )

        og.Controller.edit(
            {"graph_path": "/ActionGraph", "evaluator_name": "execution"},
            {
                og.Controller.Keys.CREATE_NODES: [
                    ("OnPlaybackTick", "omni.graph.action.OnPlaybackTick"),
                    ("PublishJointState", "isaacsim.ros2.bridge.ROS2PublishJointState"),
                    ("ReadSimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
                ],
                og.Controller.Keys.CONNECT: [
                    ("OnPlaybackTick.outputs:tick", "PublishJointState.inputs:execIn"),
                    ("ReadSimTime.outputs:simulationTime", "PublishJointState.inputs:timeStamp"),
                ],
                og.Controller.Keys.SET_VALUES: [("PublishJointState.inputs:targetPrim", "/panda")],
            },
        )

        world.play()
        for _ in range(120):
            _, wrist_position, _, wrist_orientation = get_wrist_tracking_pose()
            wrist_camera.set_world_poses(wrist_position, wrist_orientation)
            world.step(render=True)

        direct_camera_stats = {}
        for (label, _, _, _, _), sensor in zip(camera_specs, sensors, strict=True):
            rgb_data, _ = sensor.get_data("rgb")
            if rgb_data is None:
                direct_camera_stats[label] = {"available": False}
                continue
            rgb_array = rgb_data.numpy()
            direct_camera_stats[label] = {
                "available": True,
                "shape": list(rgb_array.shape),
                "dtype": str(rgb_array.dtype),
                "pixel_min": int(rgb_array.min()),
                "pixel_max": int(rgb_array.max()),
                "pixel_mean": float(rgb_array.mean()),
                "pixel_std": float(rgb_array.std()),
            }
        (RESULT_DIR / "direct_camera_stats.json").write_text(
            json.dumps(direct_camera_stats, indent=2), encoding="utf-8"
        )

        hand_world_position, hand_quaternion_wxyz = get_hand_world_pose()
        hand_quaternion_xyzw = np.roll(hand_quaternion_wxyz, -1)
        eef_pose = {
            "timestamp": time.time(),
            "source": "Isaac Sim USD panda_hand local-to-world transform",
            "source_prim": hand_path,
            "reference_frame": "/World",
            "position_unit": "meter",
            "position_xyz_m": hand_world_position.tolist(),
            "orientation_convention": "right-handed quaternion",
            "quaternion_source_order": "wxyz",
            "quaternion_wxyz": hand_quaternion_wxyz.tolist(),
            "quaternion_target_order": "xyzw",
            "quaternion_xyzw": hand_quaternion_xyzw.tolist(),
            "axis_angle_computation": "deferred to LeRobot LiberoProcessorStep",
            "joint_command_subscriber_created": False,
            "vla_action_sent": False,
        }
        (RESULT_DIR / "eef_pose.json").write_text(
            json.dumps(eef_pose, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        READY_FILE.write_text(
            json.dumps(
                {
                    "timestamp": time.time(),
                    "isaac_version": omni.kit.app.get_app().get_app_version(),
                    "renderer": "RaytracedLighting",
                    "headless": True,
                    "franka_asset": franka_asset,
                    "franka_prim": "/panda",
                    "hand_prim": hand_path,
                    "eef_pose_file": str(RESULT_DIR / "eef_pose.json"),
                    "camera_api": "isaacsim.sensors.experimental.rtx.RtxCamera + CameraSensor",
                    "publish_api": "ROS2PublishImage writer",
                    "frame_skip_count_used": False,
                    "cameras": metadata,
                    "policy_loaded": False,
                    "vla_action_sent": False,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"ISAAC_READY={READY_FILE}", flush=True)

        deadline = time.monotonic() + RUNTIME_TIMEOUT_SEC
        while app.is_running() and time.monotonic() < deadline and not STOP_FILE.exists():
            _, wrist_position, _, wrist_orientation = get_wrist_tracking_pose()
            wrist_camera.set_world_poses(wrist_position, wrist_orientation)
            world.step(render=True)
    except Exception:
        (RESULT_DIR / "isaac_exception.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        app.close()


if __name__ == "__main__":
    main()
