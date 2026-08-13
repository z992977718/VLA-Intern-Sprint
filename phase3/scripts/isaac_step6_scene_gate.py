#!/usr/bin/env python3
"""Build the audited Step 6 Isaac scene and capture pre-policy visual evidence."""

from __future__ import annotations

import argparse
import json
import math
import os
import time
import traceback
from pathlib import Path

import numpy as np
from PIL import Image

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
from isaacsim import SimulationApp

from phase3_step6_common import (
    ARM_JOINTS,
    BASKET_COLLIDERS,
    FINGER_JOINTS,
    OBJECT_APPROX_CENTERS,
    OBJECT_APPROX_HALF_EXTENTS,
    OBJECT_VISUAL_SCALES,
    PHYSICS_DT,
    PROJECT,
    RESULT,
    TABLE_TOP_HALF_EXTENTS,
    TABLE_TOP_POSITION,
    TABLE_TOP_QUATERNION_WXYZ,
    atomic_json,
    load_libero_reference,
    matrix_to_quaternion_wxyz,
    normalize_quaternion_wxyz,
    synthetic_success_tests,
    task_success,
)


def gf_quat(Gf, values: np.ndarray):
    w, x, y, z = normalize_quaternion_wxyz(values)
    return Gf.Quatd(float(w), Gf.Vec3d(float(x), float(y), float(z)))


def set_pose_scale(UsdGeom, Gf, prim, position=None, quaternion=None, scale=None) -> None:
    xform = UsdGeom.Xformable(prim)
    xform.ClearXformOpOrder()
    if position is not None:
        xform.AddTranslateOp().Set(Gf.Vec3d(*map(float, position)))
    if quaternion is not None:
        xform.AddOrientOp(UsdGeom.XformOp.PrecisionDouble).Set(gf_quat(Gf, np.asarray(quaternion)))
    if scale is not None:
        xform.AddScaleOp().Set(Gf.Vec3d(*map(float, scale)))


def add_reference(stage, UsdGeom, Gf, path: str, usd: Path, scale) -> None:
    prim = UsdGeom.Xform.Define(stage, path).GetPrim()
    prim.GetReferences().AddReference(str(usd))
    set_pose_scale(UsdGeom, Gf, prim, scale=scale)


def add_box(stage, UsdGeom, UsdPhysics, Gf, path: str, position, quaternion, half_extents, visible=False):
    cube = UsdGeom.Cube.Define(stage, path)
    cube.CreateSizeAttr(1.0)
    set_pose_scale(UsdGeom, Gf, cube.GetPrim(), position, quaternion, np.asarray(half_extents) * 2.0)
    UsdPhysics.CollisionAPI.Apply(cube.GetPrim())
    if not visible:
        cube.MakeInvisible()
    return cube.GetPrim()


def add_object(stage, UsdGeom, UsdPhysics, Gf, name: str, reference: dict, dynamic: bool) -> str:
    body_key = f"{name}_1_main"
    source_name = name
    pose = reference["body_poses"][body_key]
    root_path = f"/World/Task/{name}"
    root = UsdGeom.Xform.Define(stage, root_path).GetPrim()
    set_pose_scale(UsdGeom, Gf, root, pose["position_xyz_m"], pose["quaternion_wxyz"])
    add_reference(
        stage,
        UsdGeom,
        Gf,
        f"{root_path}/Visual",
        RESULT / "assets_usd" / f"{source_name}.usd",
        OBJECT_VISUAL_SCALES[source_name],
    )
    if name in OBJECT_APPROX_HALF_EXTENTS:
        add_box(
            stage,
            UsdGeom,
            UsdPhysics,
            Gf,
            f"{root_path}/APPROXIMATE_COLLIDER",
            OBJECT_APPROX_CENTERS[name],
            [1.0, 0.0, 0.0, 0.0],
            OBJECT_APPROX_HALF_EXTENTS[name],
        )
        if dynamic:
            UsdPhysics.RigidBodyAPI.Apply(root)
            UsdPhysics.MassAPI.Apply(root).CreateMassAttr(0.03)
    return root_path


def build_scene(app: SimulationApp, initial_state_id: int, dynamic_objects: bool):
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdPhysics
    from isaacsim.core.api import World
    from isaacsim.core.experimental.prims import Articulation
    from isaacsim.core.experimental.utils.stage import add_reference_to_stage
    from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera
    from isaacsim.storage.native import get_assets_root_path

    reference = load_libero_reference(initial_state_id)
    world = World(stage_units_in_meters=1.0, physics_dt=PHYSICS_DT, rendering_dt=PHYSICS_DT)
    stage = world.stage

    dome = UsdLux.DomeLight.Define(stage, "/World/DomeLight")
    dome.CreateIntensityAttr(850.0)
    distant = UsdLux.DistantLight.Define(stage, "/World/DistantLight")
    distant.CreateIntensityAttr(1200.0)
    distant.CreateAngleAttr(0.53)

    # Exact source visual mesh and source body transform.
    table_root = UsdGeom.Xform.Define(stage, "/World/Task/living_room_table").GetPrim()
    set_pose_scale(UsdGeom, Gf, table_root, [-0.25, 0.25, 0.0], [0.7071067812, 0.0, 0.0, 0.7071067812])
    add_reference(stage, UsdGeom, Gf, "/World/Task/living_room_table/Visual", RESULT / "assets_usd/living_room_table.usd", OBJECT_VISUAL_SCALES["living_room_table"])
    # Exact task-relevant top collision geom. Other decorative table collisions are omitted.
    add_box(stage, UsdGeom, UsdPhysics, Gf, "/World/Task/table_top_collision", TABLE_TOP_POSITION,
            TABLE_TOP_QUATERNION_WXYZ, TABLE_TOP_HALF_EXTENTS)

    basket_pose = reference["body_poses"]["basket_1_main"]
    basket_root = UsdGeom.Xform.Define(stage, "/World/Task/basket").GetPrim()
    set_pose_scale(UsdGeom, Gf, basket_root, basket_pose["position_xyz_m"], basket_pose["quaternion_wxyz"])
    add_reference(stage, UsdGeom, Gf, "/World/Task/basket/Visual", RESULT / "assets_usd/basket.usd", OBJECT_VISUAL_SCALES["basket"])
    for index, (position, quaternion, half_extents) in enumerate(BASKET_COLLIDERS):
        add_box(stage, UsdGeom, UsdPhysics, Gf, f"/World/Task/basket/collider_{index}", position, quaternion, half_extents)

    soup_path = add_object(stage, UsdGeom, UsdPhysics, Gf, "alphabet_soup", reference, dynamic_objects)
    tomato_path = add_object(stage, UsdGeom, UsdPhysics, Gf, "tomato_sauce", reference, dynamic_objects)

    robot_path = "/World/Robot"
    add_reference_to_stage(
        f"{get_assets_root_path()}/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd", robot_path
    )
    robot_prim = stage.GetPrimAtPath(robot_path)
    set_pose_scale(UsdGeom, Gf, robot_prim, reference["robot_base_position_xyz_m"], reference["robot_base_quaternion_wxyz"])
    robot = Articulation(robot_path)

    for _ in range(50):
        app.update()
    world.reset()
    world.play()
    for _ in range(20):
        world.step(render=True)
    q_arm = np.asarray(reference["robot_initial_joint_positions_rad"], dtype=np.float32)
    q_gripper = np.array([min(0.04, abs(float(reference["gripper_initial_qpos"][0]))) for _ in range(2)], dtype=np.float32)
    q0 = np.concatenate([q_arm, q_gripper])
    if tuple(robot.dof_names) != ARM_JOINTS + FINGER_JOINTS:
        raise RuntimeError(f"unexpected Franka DOF names: {robot.dof_names}")
    robot.set_dof_positions(q0)
    robot.set_dof_position_targets(q0)
    for _ in range(60):
        world.step(render=True)

    camera_data = reference["camera_poses"]
    external_rotation = np.asarray(camera_data["agentview"]["world_rotation_matrix"], dtype=np.float64)
    wrist_rotation = np.asarray(camera_data["robot0_eye_in_hand"]["world_rotation_matrix"], dtype=np.float64)
    external = RtxCamera(
        path="/World/Cameras/External",
        tick_rate=20.0,
        positions=np.asarray(camera_data["agentview"]["world_position_xyz_m"], dtype=np.float32),
        orientations=matrix_to_quaternion_wxyz(external_rotation).astype(np.float32),
    )
    wrist = RtxCamera(
        path="/World/Cameras/Wrist",
        tick_rate=20.0,
        positions=np.asarray(camera_data["robot0_eye_in_hand"]["world_position_xyz_m"], dtype=np.float32),
        orientations=matrix_to_quaternion_wxyz(wrist_rotation).astype(np.float32),
    )
    aperture_mm = 20.955
    external.camera.set_apertures(horizontal_apertures=aperture_mm, vertical_apertures=aperture_mm)
    external.camera.set_focal_lengths(aperture_mm / (2.0 * math.tan(math.radians(45.0) / 2.0)))
    wrist.camera.set_apertures(horizontal_apertures=aperture_mm, vertical_apertures=aperture_mm)
    wrist.camera.set_focal_lengths(aperture_mm / (2.0 * math.tan(math.radians(75.0) / 2.0)))
    external.camera.set_clipping_ranges(0.01, 100.0)
    wrist.camera.set_clipping_ranges(0.01, 100.0)
    external_sensor = CameraSensor(external, resolution=(256, 256), annotators=["rgb"])
    wrist_sensor = CameraSensor(wrist, resolution=(256, 256), annotators=["rgb"])
    app.update()
    for _ in range(120):
        world.step(render=True)

    return {
        "world": world,
        "stage": stage,
        "robot": robot,
        "reference": reference,
        "external_camera": external,
        "wrist_camera": wrist,
        "external_sensor": external_sensor,
        "wrist_sensor": wrist_sensor,
        "soup_path": soup_path,
        "tomato_path": tomato_path,
        "basket_path": "/World/Task/basket",
        "q0": q0,
        "Usd": Usd,
        "UsdGeom": UsdGeom,
    }


def sensor_rgb(sensor) -> np.ndarray:
    data, _ = sensor.get_data("rgb")
    array = data.numpy()
    if array.ndim == 4:
        array = array[0]
    return np.asarray(array[..., :3], dtype=np.uint8)


def prim_world_pose(stage, Usd, UsdGeom, path: str) -> tuple[np.ndarray, np.ndarray]:
    transform = UsdGeom.Xformable(stage.GetPrimAtPath(path)).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    position = np.asarray(transform.ExtractTranslation(), dtype=np.float64)
    rotation = np.asarray(transform.ExtractRotationMatrix(), dtype=np.float64)
    return position, matrix_to_quaternion_wxyz(rotation)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial-state-id", type=int, default=0)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dynamic-objects", action="store_true")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True)
    app = SimulationApp({"headless": True, "renderer": "RaytracedLighting"})
    started = time.monotonic()
    try:
        scene = build_scene(app, args.initial_state_id, dynamic_objects=args.dynamic_objects)
        external = sensor_rgb(scene["external_sensor"])
        wrist = sensor_rgb(scene["wrist_sensor"])
        Image.fromarray(external).save(output / "isaac_external.png")
        Image.fromarray(wrist).save(output / "isaac_wrist.png")
        soup_position, _ = prim_world_pose(scene["stage"], scene["Usd"], scene["UsdGeom"], scene["soup_path"])
        tomato_position, _ = prim_world_pose(scene["stage"], scene["Usd"], scene["UsdGeom"], scene["tomato_path"])
        basket_position, basket_quaternion = prim_world_pose(scene["stage"], scene["Usd"], scene["UsdGeom"], scene["basket_path"])
        initial_metric = task_success(soup_position, tomato_position, basket_position, basket_quaternion)
        tests = synthetic_success_tests()
        if not tests["pass"]:
            raise RuntimeError("success detector synthetic tests failed")
        hand = next(prim for prim in scene["stage"].Traverse() if prim.GetName() == "panda_hand")
        hand_position, hand_quaternion = prim_world_pose(scene["stage"], scene["Usd"], scene["UsdGeom"], str(hand.GetPath()))
        report = {
            "pass": True,
            "initial_state_id": args.initial_state_id,
            "dynamic_objects": args.dynamic_objects,
            "language": scene["reference"]["language"],
            "source_bddl_sha256": scene["reference"]["bddl_sha256"],
            "runtime_sec": time.monotonic() - started,
            "camera_resolution": [256, 256],
            "camera_fovy_deg": {"external": 45.0, "wrist": 75.0},
            "robot_base_pose_source": "exact LIBERO root-body pose",
            "robot_initial_arm_joints_source": "exact selected LIBERO fixed initial state",
            "gripper_mapping": "APPROXIMATE: abs(first LIBERO finger qpos) copied to both Isaac finger joints",
            "visual_assets": "exact existing LIBERO OBJ converted with Isaac Sim 6.0.1",
            "collision_assets": {
                "basket": "five exact box colliders from installed basket.xml",
                "table": "exact task-relevant table-top box collider from runtime MuJoCo model",
                "targets": "APPROXIMATE ASSET: one bounding box per target object",
            },
            "isaac_hand_position_xyz_m": hand_position.tolist(),
            "isaac_hand_quaternion_wxyz": hand_quaternion.tolist(),
            "libero_eef_position_xyz_m": scene["reference"]["eef_position_xyz_m"],
            "eef_position_delta_norm_m": float(np.linalg.norm(hand_position - np.asarray(scene["reference"]["eef_position_xyz_m"]))),
            "initial_success_metric": initial_metric,
            "images": ["isaac_external.png", "isaac_wrist.png"],
        }
        atomic_json(output / "scene_gate.json", report)
        atomic_json(output / "success_detector_tests.json", tests)
        scene["stage"].GetRootLayer().Export(str(output / "scene_gate.usda"))
        print(json.dumps(report, indent=2))
    except Exception:
        (output / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
