#!/usr/bin/env python3
"""Run one hard-reset Step 6 episode with receding-horizon K=1."""

from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from pathlib import Path

import numpy as np
from PIL import Image

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
from isaacsim import SimulationApp

from action_adapter_step4 import matrix_to_quaternion_wxyz, rotation_error_axis_angle
from isaac_step6_scene_gate import build_scene, prim_world_pose, sensor_rgb
from phase3_step6_common import (
    ARM_JOINTS,
    CONTROL_STEPS_PER_ACTION,
    EEF_OFFSET_IN_HAND_M,
    FINGER_JOINTS,
    JOINT_NAMES,
    LANGUAGE,
    MAX_CYCLES,
    PHYSICS_DT,
    atomic_json,
    quaternion_wxyz_to_matrix,
    synthetic_success_tests,
    task_success,
)


MAX_RUNTIME_SEC = 900.0
MAX_CUMULATIVE_JOINT_ENDPOINT_RAD = 20.0
MAX_CUMULATIVE_EEF_PATH_M = 2.0
MAX_JOINT_STEP_RAD = 0.05
BASE_WORKSPACE_MIN = np.array([-0.35, -0.55, 0.40], dtype=np.float64)
BASE_WORKSPACE_MAX = np.array([0.30, 0.70, 1.05], dtype=np.float64)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode-index", type=int, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.episode_index not in (0, 1, 2):
        raise ValueError("Step 6 uses exactly initial states 0, 1, 2")
    episode = args.result_dir.resolve()
    episode.mkdir(parents=True, exist_ok=True)
    if (episode / "episode_complete.json").exists():
        raise FileExistsError("refusing to overwrite completed episode")
    frames = episode / "video_frames"
    frames.mkdir(exist_ok=True)
    app = SimulationApp({"headless": True, "renderer": "RaytracedLighting"})
    started = time.monotonic()
    frame_index = 0
    cycles_completed = 0
    success = False
    termination = "exception"
    try:
        import warp as wp
        import isaacsim.robot_motion.experimental.motion_generation as mg
        from pxr import Usd, UsdGeom
        from isaacsim.core.utils.extensions import enable_extension

        tests = synthetic_success_tests()
        if not tests["pass"]:
            raise RuntimeError("success detector precondition failed")
        enable_extension("isaacsim.robot_motion.pink")
        for _ in range(10):
            app.update()
        from isaacsim.robot_motion.pink import PinkIKController, load_pink_supported_robot

        scene = build_scene(app, args.episode_index, dynamic_objects=True)
        world = scene["world"]
        stage = scene["stage"]
        robot = scene["robot"]
        reference = scene["reference"]
        hand = next(prim for prim in stage.Traverse() if prim.GetName() == "panda_hand")
        hand_path = str(hand.GetPath())

        def hand_pose() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
            position, quaternion = prim_world_pose(stage, Usd, UsdGeom, hand_path)
            return position, quaternion_wxyz_to_matrix(quaternion), quaternion

        def eef_pose() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
            hand_position, hand_rotation, _ = hand_pose()
            return hand_position + hand_rotation @ EEF_OFFSET_IN_HAND_M, hand_rotation, matrix_to_quaternion_wxyz(hand_rotation)

        initial_hand_position, initial_hand_rotation, _ = hand_pose()
        wrist_initial_position = np.asarray(reference["camera_poses"]["robot0_eye_in_hand"]["world_position_xyz_m"], dtype=np.float64)
        wrist_initial_rotation = np.asarray(reference["camera_poses"]["robot0_eye_in_hand"]["world_rotation_matrix"], dtype=np.float64)
        wrist_relative_position = initial_hand_rotation.T @ (wrist_initial_position - initial_hand_position)
        wrist_relative_rotation = initial_hand_rotation.T @ wrist_initial_rotation

        def update_wrist() -> None:
            hp, hr, _ = hand_pose()
            scene["wrist_camera"].set_world_poses(
                (hp + hr @ wrist_relative_position).astype(np.float32),
                matrix_to_quaternion_wxyz(hr @ wrist_relative_rotation).astype(np.float32),
            )

        def capture_video_frame() -> None:
            nonlocal frame_index
            Image.fromarray(sensor_rgb(scene["external_sensor"])).save(frames / f"frame_{frame_index:05d}.png")
            frame_index += 1

        pink_robot = load_pink_supported_robot("franka")
        controller = PinkIKController(
            pink_robot=pink_robot,
            robot_joint_space=list(JOINT_NAMES),
            robot_site_space=["panda_hand"],
            tool_frame="panda_hand",
            position_cost=5.0,
            orientation_cost=0.05,
            posture_cost=5e-3,
            solver="osqp",
            dt=PHYSICS_DT,
        )
        lower_raw, upper_raw = robot.get_dof_limits()
        lower = lower_raw.numpy()[0]
        upper = upper_raw.numpy()[0]

        def estimated_state():
            return mg.RobotState(
                joints=mg.JointState.from_name(
                    robot_joint_space=list(JOINT_NAMES),
                    positions=(list(JOINT_NAMES), robot.get_dof_positions()),
                    velocities=(list(JOINT_NAMES), robot.get_dof_velocities()),
                )
            )

        for _ in range(60):
            update_wrist()
            world.step(render=True)
        initial_eef_position, initial_eef_rotation, initial_eef_quaternion = eef_pose()
        initial_joint = robot.get_dof_positions().numpy()[0].copy()
        previous_joint = initial_joint.copy()
        previous_eef_position = initial_eef_position.copy()
        cumulative_joint = 0.0
        cumulative_eef = 0.0
        initial_soup_position, _ = prim_world_pose(stage, Usd, UsdGeom, scene["soup_path"])
        initial_tomato_position, _ = prim_world_pose(stage, Usd, UsdGeom, scene["tomato_path"])
        initial_basket_position, initial_basket_quaternion = prim_world_pose(stage, Usd, UsdGeom, scene["basket_path"])
        initial_metric = task_success(initial_soup_position, initial_tomato_position, initial_basket_position, initial_basket_quaternion)
        if initial_metric["success"]:
            raise RuntimeError("selected initial state is already successful")
        reset_report = {
            "episode_index": args.episode_index,
            "initial_state_id": args.episode_index,
            "hard_reset_process": True,
            "language": LANGUAGE,
            "source_robot_arm_joints_rad": reference["robot_initial_joint_positions_rad"],
            "isaac_robot_joints_after_settle_rad": initial_joint.tolist(),
            "eef_position_xyz_m": initial_eef_position.tolist(),
            "eef_quaternion_wxyz": initial_eef_quaternion.tolist(),
            "eef_offset_in_hand_m": EEF_OFFSET_IN_HAND_M.tolist(),
            "source_libero_eef_position_xyz_m": reference["eef_position_xyz_m"],
            "eef_source_delta_norm_m": float(np.linalg.norm(initial_eef_position - np.asarray(reference["eef_position_xyz_m"]))),
            "object_positions_xyz_m": {
                "alphabet_soup": initial_soup_position.tolist(),
                "tomato_sauce": initial_tomato_position.tolist(),
                "basket": initial_basket_position.tolist(),
            },
            "initial_success_metric": initial_metric,
        }
        atomic_json(episode / "reset.json", reset_report)
        capture_video_frame()

        base_position = np.asarray(reference["robot_base_position_xyz_m"], dtype=np.float64)
        base_rotation = quaternion_wxyz_to_matrix(np.asarray(reference["robot_base_quaternion_wxyz"], dtype=np.float64))
        records = []
        for cycle_index in range(MAX_CYCLES):
            if time.monotonic() - started > MAX_RUNTIME_SEC:
                termination = "max_runtime"
                break
            cycle = episode / f"cycle_{cycle_index:03d}"
            cycle.mkdir(exist_ok=False)
            for _ in range(12):
                update_wrist()
                world.step(render=True)
            camera_timestamp = time.time()
            external = sensor_rgb(scene["external_sensor"])
            wrist = sensor_rgb(scene["wrist_sensor"])
            current_eef_position, current_eef_rotation, current_eef_quaternion = eef_pose()
            joints = robot.get_dof_positions().numpy()[0]
            robot_timestamp = time.time()
            Image.fromarray(external).save(cycle / "camera_external.png")
            Image.fromarray(wrist).save(cycle / "camera_wrist.png")
            atomic_json(
                cycle / "joint_state.json",
                {
                    "topic": "Isaac direct articulation state",
                    "raw_order": list(JOINT_NAMES),
                    "position_by_name": {name: float(value) for name, value in zip(JOINT_NAMES, joints, strict=True)},
                    "timestamp": robot_timestamp,
                },
            )
            atomic_json(
                cycle / "eef_pose.json",
                {
                    "timestamp": robot_timestamp,
                    "source_prim": hand_path,
                    "reference_frame": "/World",
                    "position_unit": "meter",
                    "position_xyz_m": current_eef_position.tolist(),
                    "quaternion_wxyz": current_eef_quaternion.tolist(),
                    "quaternion_xyzw": np.roll(current_eef_quaternion, -1).tolist(),
                    "calibration": "panda_hand plus fixed audited local tool offset",
                },
            )
            observation_timestamp = max(camera_timestamp, robot_timestamp)
            atomic_json(
                cycle / "observation_ready.json",
                {
                    "episode_index": args.episode_index,
                    "cycle_index": cycle_index,
                    "initial_state_id": args.episode_index,
                    "camera_timestamp": camera_timestamp,
                    "robot_state_timestamp": robot_timestamp,
                    "observation_timestamp": observation_timestamp,
                    "image_state_skew_sec": abs(camera_timestamp - robot_timestamp),
                    "language": LANGUAGE,
                    "fresh_observation": True,
                },
            )
            response_path = cycle / "policy_response.json"
            deadline = time.monotonic() + 120.0
            while not response_path.is_file():
                if time.monotonic() > deadline:
                    raise TimeoutError("Pi0.5 inference timeout")
                time.sleep(0.01)
            response = json.loads(response_path.read_text(encoding="utf-8"))
            if response["episode_index"] != args.episode_index or response["cycle_index"] != cycle_index:
                raise RuntimeError("stale policy response")
            if response["predict_action_chunk_calls_this_cycle"] != 1 or response["action_index_authorized"] != 0:
                raise RuntimeError("receding-horizon protocol violation")
            bounded = response["bounded"]
            target_eef_position = np.asarray(bounded["target_position_xyz_m"], dtype=np.float64)
            target_eef_rotation = np.asarray(bounded["target_orientation_matrix"], dtype=np.float64)
            if np.any(target_eef_position < BASE_WORKSPACE_MIN) or np.any(target_eef_position > BASE_WORKSPACE_MAX):
                raise RuntimeError("EEF target outside audited workspace")
            target_hand_position_world = target_eef_position - target_eef_rotation @ EEF_OFFSET_IN_HAND_M
            target_hand_rotation_world = target_eef_rotation
            target_hand_position_base = base_rotation.T @ (target_hand_position_world - base_position)
            target_hand_rotation_base = base_rotation.T @ target_hand_rotation_world
            target_positions = wp.from_numpy(np.asarray([target_hand_position_base], np.float32), dtype=wp.float32, device="cpu")
            target_orientations = wp.from_numpy(
                np.asarray([matrix_to_quaternion_wxyz(target_hand_rotation_base)], np.float32), dtype=wp.float32, device="cpu"
            )
            setpoint = mg.RobotState(
                sites=mg.SpatialState.from_name(
                    spatial_space=["panda_hand"],
                    positions=(["panda_hand"], target_positions),
                    orientations=(["panda_hand"], target_orientations),
                )
            )
            if not controller.reset(estimated_state(), setpoint, cycle_index):
                raise RuntimeError("PINK reset failed")
            controller_ms = []
            last_target = None
            for step_index in range(CONTROL_STEPS_PER_ACTION):
                control_started = time.perf_counter()
                desired = controller.forward(estimated_state(), setpoint, cycle_index + step_index * PHYSICS_DT)
                controller_ms.append((time.perf_counter() - control_started) * 1000.0)
                if desired is None or desired.joints.positions is None:
                    raise RuntimeError("PINK forward failed")
                joint_target = desired.joints.positions.numpy().astype(np.float64)
                indices = desired.joints.position_indices.numpy().astype(int)
                current = robot.get_dof_positions().numpy()[0]
                if not np.isfinite(joint_target).all():
                    raise RuntimeError("non-finite joint target")
                if np.max(np.abs(joint_target - current[indices])) > MAX_JOINT_STEP_RAD:
                    raise RuntimeError("joint step safety limit")
                if np.any(joint_target < lower[indices]) or np.any(joint_target > upper[indices]):
                    raise RuntimeError("joint limit safety rejection")
                robot.set_dof_position_targets(joint_target.astype(np.float32), dof_indices=indices)
                last_target = joint_target
                if step_index == 0:
                    gripper_command = float(bounded["gripper_command"])
                    finger_target = 0.0 if gripper_command > 0.1 else (0.04 if gripper_command < -0.1 else float(np.mean(current[7:])))
                    robot.set_dof_position_targets(
                        np.array([finger_target, finger_target], dtype=np.float32),
                        dof_indices=np.array([7, 8]),
                    )
                update_wrist()
                render = step_index % 6 == 0
                world.step(render=render)
                if render:
                    capture_video_frame()
            actual_eef_position, actual_eef_rotation, _ = eef_pose()
            actual_joint = robot.get_dof_positions().numpy()[0]
            cumulative_joint += float(np.linalg.norm(actual_joint[:7] - previous_joint[:7]))
            cumulative_eef += float(np.linalg.norm(actual_eef_position - previous_eef_position))
            previous_joint = actual_joint.copy()
            previous_eef_position = actual_eef_position.copy()
            if cumulative_joint > MAX_CUMULATIVE_JOINT_ENDPOINT_RAD:
                raise RuntimeError("cumulative joint displacement safety limit")
            if cumulative_eef > MAX_CUMULATIVE_EEF_PATH_M:
                raise RuntimeError("cumulative EEF path safety limit")
            soup_position, _ = prim_world_pose(stage, Usd, UsdGeom, scene["soup_path"])
            tomato_position, _ = prim_world_pose(stage, Usd, UsdGeom, scene["tomato_path"])
            basket_position, basket_quaternion = prim_world_pose(stage, Usd, UsdGeom, scene["basket_path"])
            metric = task_success(soup_position, tomato_position, basket_position, basket_quaternion)
            record = {
                "episode_index": args.episode_index,
                "cycle_index": cycle_index,
                "initial_state_id": args.episode_index,
                "language": LANGUAGE,
                "raw_action_chunk_shape": response["chunk_shape"],
                "action_index_executed": 0,
                "remaining_actions_executed": 0,
                "raw_first_action": response["raw_first_action"],
                "bounded_action": bounded["bounded_action"],
                "eef_before_xyz_m": current_eef_position.tolist(),
                "eef_target_xyz_m": target_eef_position.tolist(),
                "eef_after_xyz_m": actual_eef_position.tolist(),
                "eef_position_error_m": float(np.linalg.norm(target_eef_position - actual_eef_position)),
                "eef_orientation_error_rad": float(np.linalg.norm(rotation_error_axis_angle(target_eef_rotation, actual_eef_rotation))),
                "last_joint_target": None if last_target is None else last_target.tolist(),
                "inference_latency_ms": response["inference_latency_ms"],
                "adapter_latency_ms": response["adapter_latency_ms"],
                "controller_latency_mean_ms": float(np.mean(controller_ms)),
                "controller_latency_p95_ms": float(np.percentile(controller_ms, 95)),
                "cumulative_joint_endpoint_displacement_rad": cumulative_joint,
                "cumulative_eef_path_m": cumulative_eef,
                "object_centers_xyz_m": {
                    "alphabet_soup": soup_position.tolist(),
                    "tomato_sauce": tomato_position.tolist(),
                    "basket": basket_position.tolist(),
                },
                "success_metric": metric,
                "safety_status": "PASS",
            }
            atomic_json(episode / f"cycle_{cycle_index:03d}.json", record)
            atomic_json(cycle / "execution_complete.json", {"cycle_index": cycle_index, "pass": True, "success": metric["success"]})
            records.append(record)
            cycles_completed = cycle_index + 1
            if metric["success"]:
                success = True
                termination = "success"
                break
        else:
            termination = "horizon_reached"
        if termination == "exception":
            termination = "horizon_reached" if cycles_completed == MAX_CYCLES else "max_runtime"
        final_eef_position, _, final_eef_quaternion = eef_pose()
        final_soup_position, _ = prim_world_pose(stage, Usd, UsdGeom, scene["soup_path"])
        final_tomato_position, _ = prim_world_pose(stage, Usd, UsdGeom, scene["tomato_path"])
        final_basket_position, final_basket_quaternion = prim_world_pose(stage, Usd, UsdGeom, scene["basket_path"])
        final_metric = task_success(final_soup_position, final_tomato_position, final_basket_position, final_basket_quaternion)
        atomic_json(
            episode / "episode_complete.json",
            {
                "episode_index": args.episode_index,
                "initial_state_id": args.episode_index,
                "completed": True,
                "success": bool(success and final_metric["success"]),
                "termination": termination,
                "cycles_completed": cycles_completed,
                "max_cycles": MAX_CYCLES,
                "runtime_sec": time.monotonic() - started,
                "frames": frame_index,
                "final_eef_position_xyz_m": final_eef_position.tolist(),
                "final_eef_quaternion_wxyz": final_eef_quaternion.tolist(),
                "final_success_metric": final_metric,
                "oom": False,
                "manual_intervention": False,
                "action_chunk_policy": "K=1; only action_chunk[0]",
            },
        )
    except Exception:
        (episode / "exception.txt").write_text(traceback.format_exc(), encoding="utf-8")
        atomic_json(
            episode / "episode_complete.json",
            {
                "episode_index": args.episode_index,
                "initial_state_id": args.episode_index,
                "completed": False,
                "success": False,
                "termination": "safety_or_runtime_exception",
                "cycles_completed": cycles_completed,
                "runtime_sec": time.monotonic() - started,
                "frames": frame_index,
                "oom": "out of memory" in traceback.format_exc().lower(),
                "manual_intervention": False,
                "exception_file": "exception.txt",
            },
        )
        raise
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
