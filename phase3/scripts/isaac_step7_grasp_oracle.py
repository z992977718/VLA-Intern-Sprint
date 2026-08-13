#!/usr/bin/env python3
"""Phase 3 / Step 7C: one hard-reset scripted grasp trial, without Pi0.5.

The target is read from the live Step 6 Isaac scene. No object pose is set
after scene reset, no attachment is created, and the gripper/object physics is
left to PhysX. This script is deliberately independent of frozen Step 6 code.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
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
from phase3_step6_common import ARM_JOINTS, FINGER_JOINTS, JOINT_NAMES, PHYSICS_DT, atomic_json, quaternion_wxyz_to_matrix
from pink_arm_only import articulation_joint_indices, independent_gripper_target


OBJECTS = {"alphabet": "alphabet_soup", "tomato": "tomato_sauce"}
TOP_DOWN_TOOL_ROTATION = np.diag([1.0, -1.0, -1.0]).astype(np.float64)
PRE_GRASP_CLEARANCE_M = 0.085
GRASP_TOP_CLEARANCE_M = 0.010
LIFT_DELTA_M = 0.060
POSITION_TOLERANCE_M = 0.015
ORIENTATION_TOLERANCE_RAD = 0.18
MAX_JOINT_STEP_RAD = 0.05
STAGE_STEPS = {"approach": 240, "descent": 200, "close_settle": 180, "lift": 240, "hold": 180}


def pose_record(stage, Usd, UsdGeom, path: str) -> dict:
    position, quaternion = prim_world_pose(stage, Usd, UsdGeom, path)
    return {"position_xyz_m": position.tolist(), "quaternion_wxyz": quaternion.tolist()}


def dynamic_object_geometry(stage, Usd, UsdGeom, path: str) -> dict:
    prim = stage.GetPrimAtPath(path + "/APPROXIMATE_COLLIDER")
    if not prim.IsValid():
        raise RuntimeError(f"Missing active collider for {path}")
    transform = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    matrix = np.asarray(transform, dtype=np.float64)
    # Cube size is 1 and ScaleOp contains the full dimensions; transform columns
    # therefore give world-space oriented half-axis lengths directly after /2.
    half_axes = matrix[:3, :3] * 0.5
    half_extents = np.linalg.norm(half_axes, axis=0)
    center = np.asarray(transform.ExtractTranslation(), dtype=np.float64)
    rotation = half_axes / half_extents
    return {
        "center_xyz_m": center.tolist(),
        "orientation_matrix": rotation.tolist(),
        "half_extents_xyz_m": half_extents.tolist(),
        "dimensions_xyz_m": (half_extents * 2.0).tolist(),
        "top_z_m": float(center[2] + np.sum(np.abs(rotation[2]) * half_extents)),
    }


def classify_failure(stages: dict, motion: dict, close_reached: bool, safety: dict) -> str:
    if not safety["pass"]:
        return "SAFETY_STOP"
    if not stages["approach"]["reached"]:
        return "APPROACH_FAILURE"
    if not stages["descent"]["reached"]:
        return "DESCENT_FAILURE"
    if not close_reached:
        return "GRIPPER_FAILURE"
    if motion["max_vertical_displacement_m"] < 0.005:
        return "GRASP_FAILURE"
    if motion["max_vertical_displacement_m"] < LIFT_DELTA_M:
        return "LIFT_FAILURE"
    if motion["final_vertical_displacement_m"] < LIFT_DELTA_M * 0.75:
        return "DROP"
    return "SUCCESS"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--object", choices=sorted(OBJECTS), required=True)
    parser.add_argument("--trial-index", type=int, choices=(0, 1, 2), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--arm-only-urdf", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite trial directory: {output}")
    output.mkdir(parents=True)
    frames = output / "video_frames"
    frames.mkdir()

    app = SimulationApp({"headless": True, "renderer": "RaytracedLighting"})
    start = time.monotonic()
    frame_index = 0
    trial_result: dict | None = None
    descent_telemetry: list[dict] = []
    pink_telemetry: list[dict] = []
    gripper_telemetry: list[dict] = []
    safety_telemetry: list[dict] = []
    try:
        import warp as wp
        import isaacsim.robot_motion.experimental.motion_generation as mg
        from pxr import Usd, UsdGeom
        from isaacsim.core.utils.extensions import enable_extension

        enable_extension("isaacsim.robot_motion.pink")
        for _ in range(10):
            app.update()
        from isaacsim.robot_motion.pink import PinkIKController, load_pink_robot

        scene = build_scene(app, 0, dynamic_objects=True)
        world, stage, robot = scene["world"], scene["stage"], scene["robot"]
        object_name = OBJECTS[args.object]
        object_path = scene["soup_path"] if object_name == "alphabet_soup" else scene["tomato_path"]
        hand = next(prim for prim in stage.Traverse() if prim.GetName() == "panda_hand")
        tool = next(prim for prim in stage.Traverse() if prim.GetName() == "tool_center")
        hand_path, tool_path = str(hand.GetPath()), str(tool.GetPath())
        source_geometry = dynamic_object_geometry(stage, Usd, UsdGeom, object_path)
        object_initial = pose_record(stage, Usd, UsdGeom, object_path)
        object_initial_position = np.asarray(object_initial["position_xyz_m"], dtype=np.float64)
        half_extents = np.asarray(source_geometry["half_extents_xyz_m"], dtype=np.float64)
        center = np.asarray(source_geometry["center_xyz_m"], dtype=np.float64)
        grasp_position = center.copy(); grasp_position[2] = source_geometry["top_z_m"] + GRASP_TOP_CLEARANCE_M
        pre_grasp_position = grasp_position.copy(); pre_grasp_position[2] += PRE_GRASP_CLEARANCE_M
        lift_position = grasp_position.copy(); lift_position[2] += LIFT_DELTA_M + PRE_GRASP_CLEARANCE_M

        base_position = np.asarray(scene["reference"]["robot_base_position_xyz_m"], dtype=np.float64)
        base_rotation = quaternion_wxyz_to_matrix(np.asarray(scene["reference"]["robot_base_quaternion_wxyz"], dtype=np.float64))
        pink_robot = load_pink_robot(args.arm_only_urdf)
        if pink_robot.model.nq != 7 or pink_robot.model.nv != 7:
            raise RuntimeError(f"IK_FAILURE: arm-only PINK model is not 7D: nq={pink_robot.model.nq}, nv={pink_robot.model.nv}")
        if pink_robot.controlled_joint_names != list(ARM_JOINTS):
            raise RuntimeError(f"IK_FAILURE: arm-only PINK joint mismatch: {pink_robot.controlled_joint_names}")
        articulation_names = list(robot.dof_names)
        arm_articulation_indices = articulation_joint_indices(articulation_names, ARM_JOINTS)
        finger_articulation_indices = articulation_joint_indices(articulation_names, FINGER_JOINTS)
        controller = PinkIKController(
            pink_robot=pink_robot, robot_joint_space=list(ARM_JOINTS),
            robot_site_space=["panda_hand"], tool_frame="panda_hand", position_cost=5.0,
            orientation_cost=0.25, posture_cost=5e-3, solver="osqp", dt=PHYSICS_DT,
        )
        lower_raw, upper_raw = robot.get_dof_limits()
        lower_source, upper_source = lower_raw.numpy()[0], upper_raw.numpy()[0]
        safety = {
            "pass": True,
            "events": [],
            "max_joint_step_rad": MAX_JOINT_STEP_RAD,
            "joint_limits_checked": True,
            "float_limit_tolerance_policy": "2 ULP of the coarsest runtime float dtype per joint limit",
        }
        joint_telemetry = []
        stage_progress = {"approach_last_passed_step": None, "descent_last_passed_step": None, "lift_last_passed_step": None}
        records, stage_results = [], {}
        object_poses = {"before": object_initial}

        def current_tool() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
            pos, quat = prim_world_pose(stage, Usd, UsdGeom, tool_path)
            return pos, quaternion_wxyz_to_matrix(quat), quat

        def current_hand() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
            pos, quat = prim_world_pose(stage, Usd, UsdGeom, hand_path)
            return pos, quaternion_wxyz_to_matrix(quat), quat

        def estimated_state():
            positions = robot.get_dof_positions().numpy()[0, arm_articulation_indices]
            velocities = robot.get_dof_velocities().numpy()[0, arm_articulation_indices]
            return mg.RobotState(joints=mg.JointState.from_name(
                robot_joint_space=list(ARM_JOINTS),
                positions=(list(ARM_JOINTS), wp.from_numpy(np.asarray([positions], np.float32), dtype=wp.float32, device="cpu")),
                velocities=(list(ARM_JOINTS), wp.from_numpy(np.asarray([velocities], np.float32), dtype=wp.float32, device="cpu")),
            ))

        def capture(label: str) -> None:
            nonlocal frame_index
            Image.fromarray(sensor_rgb(scene["external_sensor"])).save(frames / f"{frame_index:05d}_{label}.png")
            frame_index += 1

        def gripper_safety_decision(finger: float) -> tuple[np.ndarray, dict]:
            target = independent_gripper_target(finger)
            current = robot.get_dof_positions().numpy()[0]
            decision = evaluate_joint_safety(
                joint_names=list(FINGER_JOINTS),
                joint_actual_source=current[finger_articulation_indices],
                joint_target_source=target,
                joint_lower_source=lower_source[finger_articulation_indices],
                joint_upper_source=upper_source[finger_articulation_indices],
                max_joint_delta_rad=MAX_JOINT_STEP_RAD,
            )
            decision["joint_type"] = "prismatic"
            decision["position_unit"] = "m"
            decision["delta_threshold_unit"] = "m"
            return np.asarray(decision["clamped_target"], dtype=np.float32), decision

        def set_gripper(finger: float, label: str) -> dict:
            target, decision = gripper_safety_decision(finger)
            record = {"event": label, "command_target_m": float(finger), "safety": decision}
            gripper_telemetry.append(record)
            safety_telemetry.append({"stage": label, "path": "gripper", "decision": decision})
            if not decision["pass"]:
                safety["pass"] = False
                safety["events"].append({"stage": label, "path": "gripper", **decision})
                raise RuntimeError(f"SAFETY_STOP:{decision['reason_code']}")
            robot.set_dof_position_targets(target, dof_indices=finger_articulation_indices)
            for _ in range(10):
                world.step(render=True)
            q = robot.get_dof_positions().numpy()[0, finger_articulation_indices]
            capture(label)
            return {"finger1_m": float(q[0]), "finger2_m": float(q[1]), "width_m": float(q.sum()), "command_target_m": finger}

        def execute_stage(name: str, target_tool_position: np.ndarray, target_tool_rotation: np.ndarray, steps: int, finger_target: float) -> None:
            # Native USD tool_center shares panda_hand orientation and is used as
            # the measurement frame. PINK controls panda_hand, so its target uses
            # the actual runtime child-frame translation, not a fitted world offset.
            hand_position, hand_rotation, _ = current_hand()
            tool_position, _, _ = current_tool()
            hand_to_tool_local_m = hand_rotation.T @ (tool_position - hand_position)
            hand_target_position = target_tool_position - target_tool_rotation @ hand_to_tool_local_m
            hand_target_rotation = target_tool_rotation
            setpoint = mg.RobotState(sites=mg.SpatialState.from_name(
                spatial_space=["panda_hand"],
                positions=(["panda_hand"], wp.from_numpy(np.asarray([base_rotation.T @ (hand_target_position - base_position)], np.float32), dtype=wp.float32, device="cpu")),
                orientations=(["panda_hand"], wp.from_numpy(np.asarray([matrix_to_quaternion_wxyz(base_rotation.T @ hand_target_rotation)], np.float32), dtype=wp.float32, device="cpu")),
            ))
            if not controller.reset(estimated_state(), setpoint, 0):
                raise RuntimeError("IK_FAILURE: PINK reset failed")
            trajectory = []
            for index in range(steps):
                actual_position_before, actual_rotation_before, actual_quaternion_before = current_tool()
                current_source = robot.get_dof_positions().numpy()[0]
                desired = controller.forward(estimated_state(), setpoint, index * PHYSICS_DT)
                if desired is None or desired.joints.positions is None:
                    failure_record = {
                        "stage": name,
                        "control_step": index,
                        "pink_solve_status": "NO_TARGET_RETURNED",
                        "pink_configuration_nq": pink_robot.model.nq,
                        "pink_configuration_nv": pink_robot.model.nv,
                        "target_tool_xyz_m": target_tool_position.tolist(),
                        "actual_tool_xyz_m_before": actual_position_before.tolist(),
                        "arm_q_actual": current_source[arm_articulation_indices].tolist(),
                        "finger_q_actual_m": current_source[finger_articulation_indices].tolist(),
                    }
                    pink_telemetry.append(failure_record)
                    if name == "descent":
                        descent_telemetry.append(failure_record)
                    raise RuntimeError("IK_FAILURE: PINK forward failed")
                raw_joint_target_source = desired.joints.positions.numpy()
                pink_indices = desired.joints.position_indices.numpy().astype(int)
                pink_names = [ARM_JOINTS[int(index)] for index in pink_indices]
                if pink_names != list(ARM_JOINTS):
                    raise RuntimeError(f"IK_FAILURE: unexpected 7D PINK output mapping {pink_names}")
                indices = np.asarray([arm_articulation_indices[int(index)] for index in pink_indices], dtype=np.int64)
                arm_decision = evaluate_joint_safety(
                    joint_names=pink_names,
                    joint_actual_source=current_source[indices],
                    joint_target_source=raw_joint_target_source,
                    joint_lower_source=lower_source[indices],
                    joint_upper_source=upper_source[indices],
                    max_joint_delta_rad=MAX_JOINT_STEP_RAD,
                )
                finger_target_vector, finger_decision = gripper_safety_decision(finger_target)
                raw_joint_target = np.asarray(arm_decision["raw_target"], dtype=np.float64)
                joint_target = np.asarray(arm_decision["clamped_target"], dtype=np.float64)
                telemetry = {
                    "stage": name,
                    "control_step": index,
                    "pink_solve_status": "TARGET_RETURNED",
                    "pink_configuration_nq": pink_robot.model.nq,
                    "pink_configuration_nv": pink_robot.model.nv,
                    "pink_controlled_joint_names": list(pink_robot.controlled_joint_names),
                    "pink_target_finite": bool(np.isfinite(raw_joint_target).all()),
                    "target_source_dtype": arm_decision["target_source_dtype"],
                    "joint_limit_source_dtype": arm_decision["limit_source_dtype"],
                    "comparison_dtype": arm_decision["comparison_dtype"],
                    "target_tool_xyz_m": target_tool_position.tolist(),
                    "target_tool_rotation": target_tool_rotation.tolist(),
                    "actual_tool_xyz_m_before": actual_position_before.tolist(),
                    "actual_tool_quaternion_wxyz_before": actual_quaternion_before.tolist(),
                    "position_error_m_before": float(np.linalg.norm(target_tool_position - actual_position_before)),
                    "orientation_error_rad_before": float(np.linalg.norm(rotation_error_axis_angle(target_tool_rotation, actual_rotation_before))),
                    "arm_q_actual": current_source[indices].tolist(),
                    "arm_q_target_raw": raw_joint_target.tolist(),
                    "arm_q_target_commanded": joint_target.tolist(),
                    "arm_q_delta": (raw_joint_target - current_source[indices]).tolist(),
                    "finger_q_actual_m": current_source[finger_articulation_indices].tolist(),
                    "finger_gripper_target_m": finger_target_vector.tolist(),
                    "arm_safety": arm_decision,
                    "finger_safety": finger_decision,
                }
                joint_telemetry.append(telemetry)
                pink_telemetry.append({
                    "stage": name,
                    "control_step": index,
                    "status": "TARGET_RETURNED",
                    "configuration_nq": pink_robot.model.nq,
                    "configuration_nv": pink_robot.model.nv,
                    "controlled_joint_names": list(pink_robot.controlled_joint_names),
                    "arm_target": joint_target.tolist(),
                })
                gripper_telemetry.append({
                    "stage": name,
                    "control_step": index,
                    "finger_actual_m": current_source[finger_articulation_indices].tolist(),
                    "finger_target_m": finger_target_vector.tolist(),
                    "independent_from_pink": True,
                })
                safety_telemetry.append({
                    "stage": name,
                    "control_step": index,
                    "arm": arm_decision,
                    "gripper": finger_decision,
                    "pass": bool(arm_decision["pass"] and finger_decision["pass"]),
                })
                if name == "descent":
                    descent_telemetry.append(telemetry)
                if len(joint_telemetry) == 1:
                    atomic_json(
                        output / "float_tolerance_runtime.json",
                        {
                            "target_source_dtype": arm_decision["target_source_dtype"],
                            "joint_limit_source_dtype": arm_decision["limit_source_dtype"],
                            "comparison_dtype": arm_decision["comparison_dtype"],
                            "tolerance_policy": arm_decision["tolerance_policy"],
                            "per_joint_tolerance_rad": [row["tolerance"] for row in arm_decision["per_joint"]],
                            "max_joint_step_rad": MAX_JOINT_STEP_RAD,
                        },
                    )
                if index == 0:
                    atomic_json(output / f"{name}_step0.json", telemetry)
                if arm_decision["clamps"]:
                    safety["events"].extend(
                        {"stage": name, "step": index, "path": "arm", **clamp} for clamp in arm_decision["clamps"]
                    )
                if finger_decision["clamps"]:
                    safety["events"].extend(
                        {"stage": name, "step": index, "path": "gripper", **clamp} for clamp in finger_decision["clamps"]
                    )
                if not arm_decision["pass"] or not finger_decision["pass"]:
                    safety["pass"] = False
                    failed_path = "arm" if not arm_decision["pass"] else "gripper"
                    failed_decision = arm_decision if failed_path == "arm" else finger_decision
                    rejection = {
                        "stage": name,
                        "step": index,
                        "path": failed_path,
                        "reason_code": failed_decision["reason_code"],
                        "violations": failed_decision["violations"],
                        "max_abs_joint_delta": failed_decision["max_abs_joint_delta"],
                        "max_delta_joint": failed_decision["max_delta_joint"],
                    }
                    safety["events"].append(rejection)
                    atomic_json(output / "joint_telemetry.json", {"records": joint_telemetry})
                    atomic_json(output / "safety.json", safety)
                    atomic_json(output / "safety_decision.json", {"decision": "REJECT", **rejection})
                    raise RuntimeError(f"SAFETY_STOP:{failed_decision['reason_code']}")
                robot.set_dof_position_targets(joint_target.astype(np.float32), dof_indices=indices)
                robot.set_dof_position_targets(
                    finger_target_vector,
                    dof_indices=finger_articulation_indices,
                )
                world.step(render=index % 4 == 0)
                stage_progress[f"{name}_last_passed_step"] = index
                if index % 12 == 0 or index == steps - 1:
                    actual_position, actual_rotation, actual_quaternion = current_tool()
                    obj = pose_record(stage, Usd, UsdGeom, object_path)
                    trajectory.append({
                        "step": index, "target_tool_xyz_m": target_tool_position.tolist(),
                        "actual_tool_xyz_m": actual_position.tolist(), "actual_tool_quaternion_wxyz": actual_quaternion.tolist(),
                        "position_error_m": float(np.linalg.norm(target_tool_position - actual_position)),
                        "orientation_error_rad": float(np.linalg.norm(rotation_error_axis_angle(target_tool_rotation, actual_rotation))),
                        "object_position_xyz_m": obj["position_xyz_m"], "joint_target": joint_target.tolist(),
                        "joint_actual": robot.get_dof_positions().numpy()[0].tolist(),
                    })
                    capture(name)
            actual_position, actual_rotation, _ = current_tool()
            position_error = float(np.linalg.norm(target_tool_position - actual_position))
            orientation_error = float(np.linalg.norm(rotation_error_axis_angle(target_tool_rotation, actual_rotation)))
            stage_results[name] = {"target_tool_xyz_m": target_tool_position.tolist(), "actual_tool_xyz_m": actual_position.tolist(), "position_error_m": position_error, "orientation_error_rad": orientation_error, "reached": bool(position_error <= POSITION_TOLERANCE_M and orientation_error <= ORIENTATION_TOLERANCE_RAD), "samples": trajectory}
            records.extend(trajectory)

        for _ in range(60): world.step(render=True)
        capture("start")
        gripper = {"before_close": set_gripper(0.04, "open")}
        execute_stage("approach", pre_grasp_position, TOP_DOWN_TOOL_ROTATION, STAGE_STEPS["approach"], 0.04)
        object_poses["at_pre_grasp"] = pose_record(stage, Usd, UsdGeom, object_path)
        execute_stage("descent", grasp_position, TOP_DOWN_TOOL_ROTATION, STAGE_STEPS["descent"], 0.04)
        object_poses["at_grasp"] = pose_record(stage, Usd, UsdGeom, object_path)
        gripper["command_close"] = set_gripper(0.0, "close")
        for _ in range(STAGE_STEPS["close_settle"] // 2):
            robot.set_dof_position_targets(independent_gripper_target(0.0), dof_indices=finger_articulation_indices)
            world.step(render=True)
        gripper["during_contact"] = set_gripper(0.0, "during_contact")
        for _ in range(STAGE_STEPS["close_settle"] // 2):
            robot.set_dof_position_targets(independent_gripper_target(0.0), dof_indices=finger_articulation_indices)
            world.step(render=True)
        gripper["after_close"] = set_gripper(0.0, "after_close")
        object_poses["after_close"] = pose_record(stage, Usd, UsdGeom, object_path)
        execute_stage("lift", lift_position, TOP_DOWN_TOOL_ROTATION, STAGE_STEPS["lift"], 0.0)
        object_poses["at_max_lift"] = pose_record(stage, Usd, UsdGeom, object_path)
        for _ in range(STAGE_STEPS["hold"]):
            robot.set_dof_position_targets(independent_gripper_target(0.0), dof_indices=finger_articulation_indices)
            world.step(render=True)
        gripper["after_lift"] = set_gripper(0.0, "hold")
        object_poses["final"] = pose_record(stage, Usd, UsdGeom, object_path)

        positions = {key: np.asarray(value["position_xyz_m"], dtype=np.float64) for key, value in object_poses.items()}
        vertical = {key: float(value[2] - object_initial_position[2]) for key, value in positions.items()}
        motion = {"initial_position_xyz_m": object_initial_position.tolist(), "object_poses": object_poses,
                  "total_displacement_m": float(np.linalg.norm(positions["final"] - object_initial_position)),
                  "max_vertical_displacement_m": float(max(vertical.values())), "final_vertical_displacement_m": vertical["final"],
                  "lift_success_threshold_m": LIFT_DELTA_M, "support_surface": "Step 6 table_top_collision / PhysX"}
        close_target_issued = bool(gripper["command_close"]["command_target_m"] == 0.0)
        close_stable = bool(
            np.max(np.abs(np.asarray([gripper["during_contact"]["finger1_m"], gripper["during_contact"]["finger2_m"]])
                          - np.asarray([gripper["after_close"]["finger1_m"], gripper["after_close"]["finger2_m"]])))
            <= 0.002
        )
        close_reached = bool(close_target_issued and close_stable)
        gripper["close_command_completed"] = close_reached
        gripper["close_blocked_by_object_inferred"] = bool(close_reached and gripper["after_close"]["width_m"] > 0.010)
        category = classify_failure(stage_results, motion, close_reached, safety)
        result = {"trial_id": f"{args.object}_{args.trial_index:02d}", "object": object_name, "trial_index": args.trial_index,
                  "diagnostic": args.diagnostic, "counted": not args.diagnostic, "initial_state_id": 0, "hard_reset": True,
                  "failure_category": category, "success": category == "SUCCESS", "runtime_sec": time.monotonic() - start,
                  "pi05_called": False, "predict_action_chunk_called": False, "object_teleported": False,
                  "kinematic_attach_used": False, "manual_intervention": False, "physics_parameters_changed": False,
                  "orientation_source": "Isaac top-down task-space rotation diag(1,-1,-1), selected for parallel jaws to descend vertically; not derived from LIBERO state mapping",
                  "object_geometry_source": "live PhysX collider world pose and oriented bounding dimensions", "oom": False,
                  "pre_grasp_completed": stage_progress["approach_last_passed_step"] == STAGE_STEPS["approach"] - 1,
                  "descent_step0_passed": stage_progress["descent_last_passed_step"] is not None,
                  "grasp_pose_reached": bool(stage_results.get("descent", {}).get("reached", False)),
                  "close_executed": "command_close" in gripper,
                  "lift_entered": stage_progress["lift_last_passed_step"] is not None,
                  "float_tolerance_clamp_count": sum(event.get("reason", "").startswith("FLOAT_TOLERANCE_") for event in safety["events"])}
        atomic_json(output / "oracle_config.json", {"object": object_name, "pre_grasp_clearance_m": PRE_GRASP_CLEARANCE_M, "grasp_top_clearance_m": GRASP_TOP_CLEARANCE_M, "lift_delta_m": LIFT_DELTA_M, "top_down_tool_rotation": TOP_DOWN_TOOL_ROTATION.tolist(), "stage_steps": STAGE_STEPS, "physics_reused_from": "Phase 3 / Step 6 build_scene"})
        atomic_json(output / "trajectory.json", {"records": records})
        atomic_json(output / "joint_telemetry.json", {"records": joint_telemetry})
        atomic_json(output / "eef.json", {"tool_center_path": tool_path, "hand_path": hand_path, "stages": stage_results})
        atomic_json(output / "gripper.json", gripper)
        atomic_json(output / "object_motion.json", motion)
        atomic_json(output / "controller.json", {"controller": "Isaac Sim PinkIKController + OSQP + Franka", "tool_frame": "panda_hand", "pink_configuration_nq": pink_robot.model.nq, "pink_configuration_nv": pink_robot.model.nv, "pink_controlled_joint_names": list(pink_robot.controlled_joint_names), "finger_in_pink_configuration": False, "orientation_source": result["orientation_source"], "stages": stage_results})
        safety["clamp_count"] = sum(event.get("reason", "").startswith("FLOAT_TOLERANCE_") for event in safety["events"])
        safety["real_violation_count"] = sum("reason_code" in event for event in safety["events"])
        safety["stage_progress"] = stage_progress
        atomic_json(output / "safety.json", safety)
        atomic_json(output / "result.json", result)
        atomic_json(output / "trial_result.json", {**result, "trial_type": "DIAGNOSTIC / NOT COUNTED" if args.diagnostic else "FORMAL"})
        trial_result = result
    except Exception:
        message = traceback.format_exc()
        (output / "exception.txt").write_text(message, encoding="utf-8")
        if trial_result is None:
            atomic_json(output / "result.json", {"trial_id": f"{args.object}_{args.trial_index:02d}", "object": OBJECTS[args.object], "trial_index": args.trial_index, "diagnostic": args.diagnostic, "counted": not args.diagnostic, "hard_reset": True, "success": False, "failure_category": "IK_FAILURE" if "IK_FAILURE" in message else ("SAFETY_STOP" if "SAFETY_STOP" in message else "OTHER"), "pi05_called": False, "predict_action_chunk_called": False, "object_teleported": False, "kinematic_attach_used": False, "manual_intervention": False, "physics_parameters_changed": False, "oom": "out of memory" in message.lower()})
        raise
    finally:
        atomic_json(output / "descent_telemetry.json", {"records": descent_telemetry})
        atomic_json(output / "pink_telemetry.json", {"records": pink_telemetry})
        atomic_json(output / "gripper_telemetry.json", {"records": gripper_telemetry})
        atomic_json(output / "safety_telemetry.json", {"records": safety_telemetry})
        (output / "run.log").write_text("Trial completed; see result.json and exception.txt when present.\n", encoding="utf-8")
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
