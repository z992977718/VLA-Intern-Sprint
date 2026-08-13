#!/usr/bin/env python3
"""Run the single authorized Step 7D Pi0.5 post-fix diagnostic episode.

This is deliberately separate from the frozen Step 6 implementation. It reuses
the Step 6 scene, cameras, action adapter, task predicate, state 0, K=1, and
100-cycle horizon while activating only the already validated robot-side fixes.
"""

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
from joint_safety_float_limits import evaluate_joint_safety
from phase3_step6_common import (
    ARM_JOINTS,
    CONTROL_STEPS_PER_ACTION,
    FINGER_JOINTS,
    JOINT_NAMES,
    LANGUAGE,
    PHYSICS_DT,
    atomic_json,
    quaternion_wxyz_to_matrix,
    synthetic_success_tests,
    task_success,
)
from pink_arm_only import articulation_joint_indices, independent_gripper_target


MAX_RUNTIME_SEC = 900.0
MAX_CUMULATIVE_JOINT_ENDPOINT_RAD = 20.0
MAX_CUMULATIVE_EEF_PATH_M = 2.0
MAX_JOINT_STEP_RAD = 0.05
BASE_WORKSPACE_MIN = np.array([-0.35, -0.55, 0.40], dtype=np.float64)
BASE_WORKSPACE_MAX = np.array([0.30, 0.70, 1.05], dtype=np.float64)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--arm-only-urdf", type=Path, required=True)
    args = parser.parse_args()
    output = args.result_dir.resolve()
    if (output / "episode_complete.json").exists():
        raise FileExistsError("refusing to overwrite the completed Step 7D episode")
    output.mkdir(parents=True, exist_ok=True)
    frames = output / "video_frames"
    frames.mkdir(exist_ok=False)

    app = SimulationApp({"headless": True, "renderer": "RaytracedLighting"})
    started = time.monotonic()
    frame_index = 0
    cycles_completed = 0
    success = False
    termination = "exception"
    records: list[dict] = []
    safety_events: list[dict] = []
    pink_failures: list[dict] = []
    try:
        import warp as wp
        import isaacsim.robot_motion.experimental.motion_generation as mg
        from pxr import Usd, UsdGeom
        from isaacsim.core.utils.extensions import enable_extension

        detector_tests = synthetic_success_tests()
        if not detector_tests["pass"]:
            raise RuntimeError("success detector precondition failed")
        enable_extension("isaacsim.robot_motion.pink")
        for _ in range(10):
            app.update()
        from isaacsim.robot_motion.pink import PinkIKController, load_pink_robot

        scene = build_scene(app, 0, dynamic_objects=True)
        world, stage, robot = scene["world"], scene["stage"], scene["robot"]
        reference = scene["reference"]
        hand = next(prim for prim in stage.Traverse() if prim.GetName() == "panda_hand")
        tool = next(prim for prim in stage.Traverse() if prim.GetName() == "tool_center")
        hand_path, tool_path = str(hand.GetPath()), str(tool.GetPath())

        def hand_pose() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
            position, quaternion = prim_world_pose(stage, Usd, UsdGeom, hand_path)
            return position, quaternion_wxyz_to_matrix(quaternion), quaternion

        def tool_pose() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
            position, quaternion = prim_world_pose(stage, Usd, UsdGeom, tool_path)
            return position, quaternion_wxyz_to_matrix(quaternion), quaternion

        initial_hand_position, initial_hand_rotation, _ = hand_pose()
        wrist_initial_position = np.asarray(
            reference["camera_poses"]["robot0_eye_in_hand"]["world_position_xyz_m"], dtype=np.float64
        )
        wrist_initial_rotation = np.asarray(
            reference["camera_poses"]["robot0_eye_in_hand"]["world_rotation_matrix"], dtype=np.float64
        )
        wrist_relative_position = initial_hand_rotation.T @ (wrist_initial_position - initial_hand_position)
        wrist_relative_rotation = initial_hand_rotation.T @ wrist_initial_rotation

        def update_wrist() -> None:
            position, rotation, _ = hand_pose()
            scene["wrist_camera"].set_world_poses(
                (position + rotation @ wrist_relative_position).astype(np.float32),
                matrix_to_quaternion_wxyz(rotation @ wrist_relative_rotation).astype(np.float32),
            )

        def capture_video_frame() -> None:
            nonlocal frame_index
            Image.fromarray(sensor_rgb(scene["external_sensor"])).save(frames / f"frame_{frame_index:05d}.png")
            frame_index += 1

        pink_robot = load_pink_robot(args.arm_only_urdf)
        if pink_robot.model.nq != 7 or pink_robot.model.nv != 7:
            raise RuntimeError(f"IK_FAILURE: expected arm-only 7D model, got nq={pink_robot.model.nq}, nv={pink_robot.model.nv}")
        if pink_robot.controlled_joint_names != list(ARM_JOINTS):
            raise RuntimeError(f"IK_FAILURE: arm-only joint mismatch {pink_robot.controlled_joint_names}")
        articulation_names = list(robot.dof_names)
        arm_indices = articulation_joint_indices(articulation_names, ARM_JOINTS)
        finger_indices = articulation_joint_indices(articulation_names, FINGER_JOINTS)
        controller = PinkIKController(
            pink_robot=pink_robot,
            robot_joint_space=list(ARM_JOINTS),
            robot_site_space=["panda_hand"],
            tool_frame="panda_hand",
            position_cost=5.0,
            orientation_cost=0.05,
            posture_cost=5e-3,
            solver="osqp",
            dt=PHYSICS_DT,
        )
        lower_raw, upper_raw = robot.get_dof_limits()
        lower_source, upper_source = lower_raw.numpy()[0], upper_raw.numpy()[0]

        def estimated_state():
            q = robot.get_dof_positions().numpy()[0, arm_indices]
            qd = robot.get_dof_velocities().numpy()[0, arm_indices]
            return mg.RobotState(
                joints=mg.JointState.from_name(
                    robot_joint_space=list(ARM_JOINTS),
                    positions=(
                        list(ARM_JOINTS),
                        wp.from_numpy(np.asarray([q], np.float32), dtype=wp.float32, device="cpu"),
                    ),
                    velocities=(
                        list(ARM_JOINTS),
                        wp.from_numpy(np.asarray([qd], np.float32), dtype=wp.float32, device="cpu"),
                    ),
                )
            )

        for _ in range(60):
            update_wrist()
            world.step(render=True)
        initial_tool_position, initial_tool_rotation, initial_tool_quaternion = tool_pose()
        initial_joint = robot.get_dof_positions().numpy()[0].copy()
        previous_joint = initial_joint.copy()
        previous_tool_position = initial_tool_position.copy()
        cumulative_joint = 0.0
        cumulative_eef = 0.0
        initial_soup_position, initial_soup_quaternion = prim_world_pose(stage, Usd, UsdGeom, scene["soup_path"])
        initial_tomato_position, initial_tomato_quaternion = prim_world_pose(stage, Usd, UsdGeom, scene["tomato_path"])
        initial_basket_position, initial_basket_quaternion = prim_world_pose(stage, Usd, UsdGeom, scene["basket_path"])
        initial_metric = task_success(
            initial_soup_position, initial_tomato_position, initial_basket_position, initial_basket_quaternion
        )
        if initial_metric["success"]:
            raise RuntimeError("selected initial state is already successful")
        atomic_json(
            output / "reset.json",
            {
                "episode_index": 0,
                "initial_state_id": 0,
                "diagnostic_not_counted": True,
                "hard_reset_process": True,
                "language": LANGUAGE,
                "source_robot_arm_joints_rad": reference["robot_initial_joint_positions_rad"],
                "isaac_robot_joints_after_settle_rad": initial_joint.tolist(),
                "eef_position_source": tool_path,
                "eef_position_xyz_m": initial_tool_position.tolist(),
                "eef_quaternion_wxyz": initial_tool_quaternion.tolist(),
                "orientation_additional_fix": False,
                "timestamp_additional_fix": False,
                "state_mapping_gripper": "[finger1, -finger2] in policy input only",
                "pink_configuration_nq": 7,
                "pink_configuration_nv": 7,
                "pink_joint_space": list(ARM_JOINTS),
                "independent_gripper": True,
                "object_poses": {
                    "alphabet_soup": {"position_xyz_m": initial_soup_position.tolist(), "quaternion_wxyz": initial_soup_quaternion.tolist()},
                    "tomato_sauce": {"position_xyz_m": initial_tomato_position.tolist(), "quaternion_wxyz": initial_tomato_quaternion.tolist()},
                    "basket": {"position_xyz_m": initial_basket_position.tolist(), "quaternion_wxyz": initial_basket_quaternion.tolist()},
                },
                "initial_success_metric": initial_metric,
            },
        )
        capture_video_frame()

        base_position = np.asarray(reference["robot_base_position_xyz_m"], dtype=np.float64)
        base_rotation = quaternion_wxyz_to_matrix(
            np.asarray(reference["robot_base_quaternion_wxyz"], dtype=np.float64)
        )
        for cycle_index in range(100):
            if time.monotonic() - started > MAX_RUNTIME_SEC:
                termination = "MAX_RUNTIME"
                break
            cycle = output / f"cycle_{cycle_index:03d}"
            cycle.mkdir(exist_ok=False)
            for _ in range(12):
                update_wrist()
                world.step(render=True)
            external = sensor_rgb(scene["external_sensor"])
            external_timestamp = time.time()
            wrist = sensor_rgb(scene["wrist_sensor"])
            wrist_timestamp = time.time()
            current_tool_position, current_tool_rotation, current_tool_quaternion = tool_pose()
            joints_before = robot.get_dof_positions().numpy()[0].copy()
            robot_timestamp = time.time()
            soup_before, soup_quaternion_before = prim_world_pose(stage, Usd, UsdGeom, scene["soup_path"])
            tomato_before, tomato_quaternion_before = prim_world_pose(stage, Usd, UsdGeom, scene["tomato_path"])
            frame_start = frame_index
            Image.fromarray(external).save(cycle / "camera_external.png")
            Image.fromarray(wrist).save(cycle / "camera_wrist.png")
            atomic_json(
                cycle / "joint_state.json",
                {
                    "topic": "Isaac direct articulation state",
                    "raw_order": list(JOINT_NAMES),
                    "position_by_name": {
                        name: float(value) for name, value in zip(JOINT_NAMES, joints_before, strict=True)
                    },
                    "timestamp": robot_timestamp,
                },
            )
            atomic_json(
                cycle / "eef_pose.json",
                {
                    "timestamp": robot_timestamp,
                    "source_prim": tool_path,
                    "reference_frame": "/World",
                    "position_unit": "meter",
                    "position_xyz_m": current_tool_position.tolist(),
                    "quaternion_wxyz": current_tool_quaternion.tolist(),
                    "quaternion_xyzw": np.roll(current_tool_quaternion, -1).tolist(),
                    "calibration": "native Isaac USD tool_center; no fitted world offset",
                    "orientation_additional_fix": False,
                },
            )
            observation_timestamp = max(external_timestamp, wrist_timestamp, robot_timestamp)
            skew = max(
                abs(external_timestamp - robot_timestamp),
                abs(wrist_timestamp - robot_timestamp),
            )
            atomic_json(
                cycle / "observation_ready.json",
                {
                    "episode_index": 0,
                    "cycle_index": cycle_index,
                    "initial_state_id": 0,
                    "diagnostic_not_counted": True,
                    "camera_external_timestamp": external_timestamp,
                    "camera_wrist_timestamp": wrist_timestamp,
                    "camera_timestamp": max(external_timestamp, wrist_timestamp),
                    "robot_state_timestamp": robot_timestamp,
                    "observation_timestamp": observation_timestamp,
                    "image_state_skew_sec": skew,
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
            sample = json.loads((cycle / "policy_input_sample.json").read_text(encoding="utf-8"))
            if response["episode_index"] != 0 or response["cycle_index"] != cycle_index:
                raise RuntimeError("stale policy response")
            if response["predict_action_chunk_calls_this_cycle"] != 1 or response["action_index_authorized"] != 0:
                raise RuntimeError("receding-horizon protocol violation")
            if response["chunk_shape"] != [1, 50, 7] or not response["chunk_finite"]:
                raise RuntimeError("Pi0.5 action chunk contract violation")

            bounded = response["bounded"]
            target_tool_position = np.asarray(bounded["target_position_xyz_m"], dtype=np.float64)
            target_tool_rotation = np.asarray(bounded["target_orientation_matrix"], dtype=np.float64)
            if np.any(target_tool_position < BASE_WORKSPACE_MIN) or np.any(target_tool_position > BASE_WORKSPACE_MAX):
                raise RuntimeError("SAFETY_STOP: EEF target outside audited workspace")
            hand_position, hand_rotation, _ = hand_pose()
            measured_tool_position, _, _ = tool_pose()
            hand_to_tool_local = hand_rotation.T @ (measured_tool_position - hand_position)
            target_hand_position = target_tool_position - target_tool_rotation @ hand_to_tool_local
            target_hand_rotation = target_tool_rotation
            setpoint = mg.RobotState(
                sites=mg.SpatialState.from_name(
                    spatial_space=["panda_hand"],
                    positions=(
                        ["panda_hand"],
                        wp.from_numpy(
                            np.asarray([base_rotation.T @ (target_hand_position - base_position)], np.float32),
                            dtype=wp.float32,
                            device="cpu",
                        ),
                    ),
                    orientations=(
                        ["panda_hand"],
                        wp.from_numpy(
                            np.asarray([matrix_to_quaternion_wxyz(base_rotation.T @ target_hand_rotation)], np.float32),
                            dtype=wp.float32,
                            device="cpu",
                        ),
                    ),
                )
            )
            if not controller.reset(estimated_state(), setpoint, cycle_index):
                pink_failures.append({"cycle": cycle_index, "stage": "reset", "reason": "PINK_RESET_FAILED"})
                raise RuntimeError("IK_FAILURE: PINK reset failed")

            gripper_command = float(bounded["gripper_command"])
            if gripper_command > 0.1:
                finger_target_scalar = 0.0
                gripper_mode = "CLOSE"
            elif gripper_command < -0.1:
                finger_target_scalar = 0.04
                gripper_mode = "OPEN"
            else:
                finger_target_scalar = float(np.mean(joints_before[finger_indices]))
                gripper_mode = "HOLD"
            finger_target = independent_gripper_target(finger_target_scalar)
            controller_steps: list[dict] = []
            controller_ms: list[float] = []
            last_arm_target: np.ndarray | None = None
            for control_step in range(CONTROL_STEPS_PER_ACTION):
                control_started = time.perf_counter()
                desired = controller.forward(
                    estimated_state(), setpoint, cycle_index + control_step * PHYSICS_DT
                )
                controller_ms.append((time.perf_counter() - control_started) * 1000.0)
                if desired is None or desired.joints.positions is None:
                    failure = {"cycle": cycle_index, "control_step": control_step, "reason": "PINK_FORWARD_FAILED"}
                    pink_failures.append(failure)
                    raise RuntimeError("IK_FAILURE: PINK forward failed")
                raw_arm_target = desired.joints.positions.numpy()
                pink_indices = desired.joints.position_indices.numpy().astype(int)
                pink_names = [ARM_JOINTS[int(index)] for index in pink_indices]
                if pink_names != list(ARM_JOINTS):
                    raise RuntimeError(f"IK_FAILURE: unexpected PINK output mapping {pink_names}")
                command_indices = np.asarray([arm_indices[int(index)] for index in pink_indices], dtype=np.int64)
                current = robot.get_dof_positions().numpy()[0]
                arm_decision = evaluate_joint_safety(
                    joint_names=pink_names,
                    joint_actual_source=current[command_indices],
                    joint_target_source=raw_arm_target,
                    joint_lower_source=lower_source[command_indices],
                    joint_upper_source=upper_source[command_indices],
                    max_joint_delta_rad=MAX_JOINT_STEP_RAD,
                )
                finger_decision = evaluate_joint_safety(
                    joint_names=list(FINGER_JOINTS),
                    joint_actual_source=current[finger_indices],
                    joint_target_source=finger_target,
                    joint_lower_source=lower_source[finger_indices],
                    joint_upper_source=upper_source[finger_indices],
                    max_joint_delta_rad=MAX_JOINT_STEP_RAD,
                )
                arm_target = np.asarray(arm_decision["clamped_target"], dtype=np.float32)
                compact = {
                    "control_step": control_step,
                    "arm_q_actual": current[command_indices].tolist(),
                    "arm_q_target_raw": np.asarray(raw_arm_target, dtype=np.float64).tolist(),
                    "arm_q_target_commanded": arm_target.tolist(),
                    "arm_safety_pass": arm_decision["pass"],
                    "arm_safety_reason": arm_decision["reason_code"],
                    "arm_max_abs_joint_delta": arm_decision["max_abs_joint_delta"],
                    "arm_clamps": arm_decision["clamps"],
                    "finger_q_actual_m": current[finger_indices].tolist(),
                    "finger_q_target_m": finger_target.tolist(),
                    "finger_safety_pass": finger_decision["pass"],
                    "finger_safety_reason": finger_decision["reason_code"],
                    "finger_clamps": finger_decision["clamps"],
                }
                controller_steps.append(compact)
                if arm_decision["clamps"] or finger_decision["clamps"]:
                    safety_events.append({"cycle": cycle_index, **compact})
                if not arm_decision["pass"] or not finger_decision["pass"]:
                    failed = arm_decision if not arm_decision["pass"] else finger_decision
                    safety_events.append(
                        {
                            "cycle": cycle_index,
                            "control_step": control_step,
                            "reason": failed["reason_code"],
                            "violations": failed["violations"],
                        }
                    )
                    atomic_json(cycle / "controller_telemetry.json", {"records": controller_steps})
                    raise RuntimeError(f"SAFETY_STOP:{failed['reason_code']}")
                robot.set_dof_position_targets(arm_target, dof_indices=command_indices)
                robot.set_dof_position_targets(finger_target, dof_indices=finger_indices)
                last_arm_target = arm_target.astype(np.float64)
                update_wrist()
                render = control_step % 6 == 0
                world.step(render=render)
                if render:
                    capture_video_frame()
            atomic_json(cycle / "controller_telemetry.json", {"records": controller_steps})

            actual_tool_position, actual_tool_rotation, actual_tool_quaternion = tool_pose()
            actual_joint = robot.get_dof_positions().numpy()[0]
            cumulative_joint += float(np.linalg.norm(actual_joint[arm_indices] - previous_joint[arm_indices]))
            cumulative_eef += float(np.linalg.norm(actual_tool_position - previous_tool_position))
            previous_joint = actual_joint.copy()
            previous_tool_position = actual_tool_position.copy()
            if cumulative_joint > MAX_CUMULATIVE_JOINT_ENDPOINT_RAD:
                raise RuntimeError("SAFETY_STOP: cumulative joint displacement limit")
            if cumulative_eef > MAX_CUMULATIVE_EEF_PATH_M:
                raise RuntimeError("SAFETY_STOP: cumulative EEF path limit")

            soup_after, soup_quaternion_after = prim_world_pose(stage, Usd, UsdGeom, scene["soup_path"])
            tomato_after, tomato_quaternion_after = prim_world_pose(stage, Usd, UsdGeom, scene["tomato_path"])
            basket_position, basket_quaternion = prim_world_pose(stage, Usd, UsdGeom, scene["basket_path"])
            metric = task_success(soup_after, tomato_after, basket_position, basket_quaternion)
            record = {
                "episode_index": 0,
                "cycle_index": cycle_index,
                "initial_state_id": 0,
                "diagnostic_not_counted": True,
                "timestamps": {
                    "camera_external": external_timestamp,
                    "camera_wrist": wrist_timestamp,
                    "joint_state": robot_timestamp,
                    "observation": observation_timestamp,
                    "image_state_max_skew_sec": skew,
                },
                "language": LANGUAGE,
                "policy_state_vector_8d": sample["robot_state_8d"],
                "policy_state_finite": sample["finite"],
                "eef_position_source": tool_path,
                "eef_before_xyz_m": current_tool_position.tolist(),
                "eef_before_quaternion_wxyz": current_tool_quaternion.tolist(),
                "eef_target_xyz_m": target_tool_position.tolist(),
                "eef_target_quaternion_wxyz": bounded["target_quaternion_wxyz"],
                "eef_after_xyz_m": actual_tool_position.tolist(),
                "eef_after_quaternion_wxyz": actual_tool_quaternion.tolist(),
                "eef_position_error_m": float(np.linalg.norm(target_tool_position - actual_tool_position)),
                "eef_orientation_error_rad": float(
                    np.linalg.norm(rotation_error_axis_angle(target_tool_rotation, actual_tool_rotation))
                ),
                "raw_action_chunk_shape": response["chunk_shape"],
                "action_index_executed": 0,
                "remaining_actions_executed": 0,
                "raw_first_action": response["raw_first_action"],
                "bounded_action": bounded["bounded_action"],
                "action_clipping_applied": bounded["clipping_applied"],
                "translation_delta_m": bounded["translation_delta_m"],
                "rotation_delta_axis_angle_rad": bounded["rotation_delta_axis_angle_rad"],
                "target_hand_position_xyz_m": target_hand_position.tolist(),
                "hand_to_tool_local_m": hand_to_tool_local.tolist(),
                "pink_arm_target_first": controller_steps[0]["arm_q_target_commanded"],
                "pink_arm_target_last": None if last_arm_target is None else last_arm_target.tolist(),
                "pink_configuration_nq": 7,
                "pink_configuration_nv": 7,
                "gripper": {
                    "policy_command": gripper_command,
                    "mode": gripper_mode,
                    "target_finger_qpos_m": finger_target.tolist(),
                    "actual_before_finger_qpos_m": joints_before[finger_indices].tolist(),
                    "actual_after_finger_qpos_m": actual_joint[finger_indices].tolist(),
                    "close_attempt": gripper_mode == "CLOSE",
                    "independent_from_pink": True,
                },
                "safety_decision": "PASS",
                "controller_step_count": len(controller_steps),
                "controller_latency_mean_ms": float(np.mean(controller_ms)),
                "controller_latency_p95_ms": float(np.percentile(controller_ms, 95)),
                "inference_latency_ms": response["inference_latency_ms"],
                "adapter_latency_ms": response["adapter_latency_ms"],
                "cumulative_joint_endpoint_displacement_rad": cumulative_joint,
                "cumulative_eef_endpoint_path_m": cumulative_eef,
                "object_poses_before": {
                    "alphabet_soup": {"position_xyz_m": soup_before.tolist(), "quaternion_wxyz": soup_quaternion_before.tolist()},
                    "tomato_sauce": {"position_xyz_m": tomato_before.tolist(), "quaternion_wxyz": tomato_quaternion_before.tolist()},
                },
                "object_poses_after": {
                    "alphabet_soup": {"position_xyz_m": soup_after.tolist(), "quaternion_wxyz": soup_quaternion_after.tolist()},
                    "tomato_sauce": {"position_xyz_m": tomato_after.tolist(), "quaternion_wxyz": tomato_quaternion_after.tolist()},
                    "basket": {"position_xyz_m": basket_position.tolist(), "quaternion_wxyz": basket_quaternion.tolist()},
                },
                "distances_m": {
                    "tool_center_to_alphabet_before": float(np.linalg.norm(current_tool_position - soup_before)),
                    "tool_center_to_tomato_before": float(np.linalg.norm(current_tool_position - tomato_before)),
                    "tool_center_to_alphabet_after": float(np.linalg.norm(actual_tool_position - soup_after)),
                    "tool_center_to_tomato_after": float(np.linalg.norm(actual_tool_position - tomato_after)),
                    "separate_gripper_center_metric": "NOT_SEPARATELY_RECONSTRUCTED",
                },
                "success_metric": metric,
                "video_frame_range": {"start_inclusive": frame_start, "end_inclusive": frame_index - 1},
            }
            atomic_json(output / f"cycle_{cycle_index:03d}.json", record)
            atomic_json(
                cycle / "execution_complete.json",
                {"cycle_index": cycle_index, "pass": True, "success": metric["success"]},
            )
            records.append(record)
            cycles_completed = cycle_index + 1
            if metric["success"]:
                success = True
                termination = "SUCCESS"
                break
        else:
            termination = "HORIZON_REACHED"
        if termination == "exception":
            termination = "HORIZON_REACHED" if cycles_completed == 100 else "MAX_RUNTIME"

        final_tool_position, _, final_tool_quaternion = tool_pose()
        final_soup_position, final_soup_quaternion = prim_world_pose(stage, Usd, UsdGeom, scene["soup_path"])
        final_tomato_position, final_tomato_quaternion = prim_world_pose(stage, Usd, UsdGeom, scene["tomato_path"])
        final_basket_position, final_basket_quaternion = prim_world_pose(stage, Usd, UsdGeom, scene["basket_path"])
        final_metric = task_success(
            final_soup_position, final_tomato_position, final_basket_position, final_basket_quaternion
        )
        atomic_json(
            output / "final_state.json",
            {
                "eef_position_xyz_m": final_tool_position.tolist(),
                "eef_quaternion_wxyz": final_tool_quaternion.tolist(),
                "object_poses": {
                    "alphabet_soup": {"position_xyz_m": final_soup_position.tolist(), "quaternion_wxyz": final_soup_quaternion.tolist()},
                    "tomato_sauce": {"position_xyz_m": final_tomato_position.tolist(), "quaternion_wxyz": final_tomato_quaternion.tolist()},
                    "basket": {"position_xyz_m": final_basket_position.tolist(), "quaternion_wxyz": final_basket_quaternion.tolist()},
                },
                "success_metric": final_metric,
            },
        )
        atomic_json(output / "cycle_telemetry.json", {"records": records})
        atomic_json(
            output / "episode_complete.json",
            {
                "episode_index": 0,
                "initial_state_id": 0,
                "diagnostic_not_counted": True,
                "completed": True,
                "success": bool(success and final_metric["success"]),
                "termination": termination,
                "cycles_completed": cycles_completed,
                "max_cycles": 100,
                "K": 1,
                "runtime_sec": time.monotonic() - started,
                "frames": frame_index,
                "oom": False,
                "manual_intervention": False,
                "action_chunk_policy": "K=1; only action_chunk[0]",
                "safety_event_count": len(safety_events),
                "pink_failure_count": len(pink_failures),
            },
        )
    except Exception:
        error = traceback.format_exc()
        (output / "exception.txt").write_text(error, encoding="utf-8")
        atomic_json(output / "cycle_telemetry.json", {"records": records})
        if not (output / "episode_complete.json").exists():
            atomic_json(
                output / "episode_complete.json",
                {
                    "episode_index": 0,
                    "initial_state_id": 0,
                    "diagnostic_not_counted": True,
                    "completed": False,
                    "success": False,
                    "termination": "SAFETY_OR_RUNTIME_EXCEPTION",
                    "cycles_completed": cycles_completed,
                    "max_cycles": 100,
                    "K": 1,
                    "runtime_sec": time.monotonic() - started,
                    "frames": frame_index,
                    "oom": "out of memory" in error.lower(),
                    "manual_intervention": False,
                    "exception_file": "exception.txt",
                    "safety_event_count": len(safety_events),
                    "pink_failure_count": len(pink_failures),
                },
            )
        raise
    finally:
        atomic_json(output / "runtime_safety_events.json", {"events": safety_events})
        atomic_json(output / "pink_failures.json", {"events": pink_failures})
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
