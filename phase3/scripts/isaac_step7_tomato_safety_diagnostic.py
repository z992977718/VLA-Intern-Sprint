#!/usr/bin/env python3
"""Phase 3 / Step 7C.2: one telemetry-only tomato safety diagnostic.

This is deliberately separate from the frozen Step 7C Oracle. It reuses the
same state-0 scene, target construction, PINK controller, safety threshold and
trajectory. The trial is DIAGNOSTIC / NOT COUNTED and stops immediately on a
safety rejection, or after three descent control steps if no rejection occurs.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
from isaacsim import SimulationApp

from action_adapter_step4 import matrix_to_quaternion_wxyz, rotation_error_axis_angle
from isaac_step6_scene_gate import build_scene, prim_world_pose
from isaac_step7_grasp_oracle import (
    GRASP_TOP_CLEARANCE_M,
    MAX_JOINT_STEP_RAD,
    PRE_GRASP_CLEARANCE_M,
    STAGE_STEPS,
    TOP_DOWN_TOOL_ROTATION,
    dynamic_object_geometry,
)
from phase3_step6_common import JOINT_NAMES, PHYSICS_DT, atomic_json, quaternion_wxyz_to_matrix


MAX_DIAGNOSTIC_DESCENT_STEPS = 3


class DiagnosticSafetyStop(RuntimeError):
    """Expected stop after persisting a rejected safety decision."""


def finite_float(value: float) -> float | None:
    return float(value) if np.isfinite(value) else None


def environment_text() -> str:
    try:
        gpu = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu",
                "--format=csv,noheader",
            ],
            text=True,
        ).strip()
    except Exception as exc:  # pragma: no cover - diagnostic fallback
        gpu = f"unavailable: {exc}"
    return (
        "phase=Phase 3 / Step 7C.2\n"
        "mode=DIAGNOSTIC / NOT COUNTED\n"
        f"python={sys.version.split()[0]}\n"
        f"python_executable={sys.executable}\n"
        f"platform={platform.platform()}\n"
        f"gpu={gpu}\n"
        "pi05_called=false\n"
        "predict_action_chunk_called=false\n"
        "physics_changed=false\n"
        "safety_threshold_changed=false\n"
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite diagnostic directory: {output}")
    output.mkdir(parents=True)
    (output / "environment.txt").write_text(environment_text(), encoding="utf-8")

    config = {
        "phase": "Phase 3 / Step 7C.2",
        "diagnostic": True,
        "counted": False,
        "object": "tomato_sauce",
        "initial_state_id": 0,
        "hard_reset": True,
        "pre_grasp_clearance_m": PRE_GRASP_CLEARANCE_M,
        "grasp_top_clearance_m": GRASP_TOP_CLEARANCE_M,
        "top_down_tool_rotation": TOP_DOWN_TOOL_ROTATION.tolist(),
        "approach_steps": STAGE_STEPS["approach"],
        "original_descent_steps": STAGE_STEPS["descent"],
        "diagnostic_descent_steps_max": MAX_DIAGNOSTIC_DESCENT_STEPS,
        "max_joint_step_rad": MAX_JOINT_STEP_RAD,
        "physics_dt_sec": PHYSICS_DT,
        "trajectory_changed": False,
        "physics_changed": False,
        "controller_changed": False,
        "safety_threshold_changed": False,
        "formal_results_modified": False,
    }
    atomic_json(output / "diagnostic_config.json", config)

    app = SimulationApp({"headless": True, "renderer": "RaytracedLighting"})
    started = time.monotonic()
    log_lines = ["Step 7C.2 tomato diagnostic started."]
    telemetry_records: list[dict] = []
    pink_records: list[dict] = []
    final_decision: dict | None = None
    descent_entered = False
    descent_step_reached: int | None = None
    outcome = "UNKNOWN"

    try:
        import warp as wp
        import isaacsim.robot_motion.experimental.motion_generation as mg
        from pxr import Usd, UsdGeom
        from isaacsim.core.utils.extensions import enable_extension

        enable_extension("isaacsim.robot_motion.pink")
        for _ in range(10):
            app.update()
        from isaacsim.robot_motion.pink import PinkIKController, load_pink_supported_robot

        scene = build_scene(app, 0, dynamic_objects=True)
        world, stage, robot = scene["world"], scene["stage"], scene["robot"]
        object_path = scene["tomato_path"]
        hand = next(prim for prim in stage.Traverse() if prim.GetName() == "panda_hand")
        tool = next(prim for prim in stage.Traverse() if prim.GetName() == "tool_center")
        hand_path, tool_path = str(hand.GetPath()), str(tool.GetPath())

        source_geometry = dynamic_object_geometry(stage, Usd, UsdGeom, object_path)
        center = np.asarray(source_geometry["center_xyz_m"], dtype=np.float64)
        grasp_position = center.copy()
        grasp_position[2] = source_geometry["top_z_m"] + GRASP_TOP_CLEARANCE_M
        pre_grasp_position = grasp_position.copy()
        pre_grasp_position[2] += PRE_GRASP_CLEARANCE_M

        base_position = np.asarray(scene["reference"]["robot_base_position_xyz_m"], dtype=np.float64)
        base_rotation = quaternion_wxyz_to_matrix(
            np.asarray(scene["reference"]["robot_base_quaternion_wxyz"], dtype=np.float64)
        )
        controller = PinkIKController(
            pink_robot=load_pink_supported_robot("franka"),
            robot_joint_space=list(JOINT_NAMES),
            robot_site_space=["panda_hand"],
            tool_frame="panda_hand",
            position_cost=5.0,
            orientation_cost=0.25,
            posture_cost=5e-3,
            solver="osqp",
            dt=PHYSICS_DT,
        )
        lower_raw, upper_raw = robot.get_dof_limits()
        lower = lower_raw.numpy()[0].astype(np.float64)
        upper = upper_raw.numpy()[0].astype(np.float64)

        def current_tool() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
            position, quaternion = prim_world_pose(stage, Usd, UsdGeom, tool_path)
            return position, quaternion_wxyz_to_matrix(quaternion), quaternion

        def current_hand() -> tuple[np.ndarray, np.ndarray]:
            position, quaternion = prim_world_pose(stage, Usd, UsdGeom, hand_path)
            return position, quaternion_wxyz_to_matrix(quaternion)

        def estimated_state():
            return mg.RobotState(
                joints=mg.JointState.from_name(
                    robot_joint_space=list(JOINT_NAMES),
                    positions=(list(JOINT_NAMES), robot.get_dof_positions()),
                    velocities=(list(JOINT_NAMES), robot.get_dof_velocities()),
                )
            )

        def persist_history() -> None:
            atomic_json(output / "pink_output.json", {"records": pink_records})
            atomic_json(output / "joint_telemetry.json", {"records": telemetry_records})

        def execute_stage(
            name: str,
            target_tool_position: np.ndarray,
            target_tool_rotation: np.ndarray,
            original_steps: int,
            executed_steps: int,
            finger_target: float,
        ) -> None:
            nonlocal final_decision, descent_entered, descent_step_reached
            if name == "descent":
                descent_entered = True

            hand_position, hand_rotation = current_hand()
            tool_position, _, _ = current_tool()
            hand_to_tool_local_m = hand_rotation.T @ (tool_position - hand_position)
            hand_target_position = target_tool_position - target_tool_rotation @ hand_to_tool_local_m
            setpoint = mg.RobotState(
                sites=mg.SpatialState.from_name(
                    spatial_space=["panda_hand"],
                    positions=(
                        ["panda_hand"],
                        wp.from_numpy(
                            np.asarray([base_rotation.T @ (hand_target_position - base_position)], np.float32),
                            dtype=wp.float32,
                            device="cpu",
                        ),
                    ),
                    orientations=(
                        ["panda_hand"],
                        wp.from_numpy(
                            np.asarray(
                                [matrix_to_quaternion_wxyz(base_rotation.T @ target_tool_rotation)], np.float32
                            ),
                            dtype=wp.float32,
                            device="cpu",
                        ),
                    ),
                )
            )
            reset_ok = bool(controller.reset(estimated_state(), setpoint, 0))
            if not reset_ok:
                raise RuntimeError("IK_FAILURE: PINK reset failed")

            for index in range(executed_steps):
                if name == "descent":
                    descent_step_reached = index
                desired = controller.forward(estimated_state(), setpoint, index * PHYSICS_DT)
                solve_status = "TARGET_RETURNED"
                if desired is None or desired.joints.positions is None:
                    solve_status = "NO_JOINT_TARGET"
                    raise RuntimeError("IK_FAILURE: PINK forward failed")

                joint_target = desired.joints.positions.numpy().astype(np.float64)
                indices = desired.joints.position_indices.numpy().astype(int)
                joint_actual_full = robot.get_dof_positions().numpy()[0].astype(np.float64)
                joint_actual = joint_actual_full[indices]
                joint_lower = lower[indices]
                joint_upper = upper[indices]
                joint_delta = joint_target - joint_actual
                abs_joint_delta = np.abs(joint_delta)
                lower_margin = joint_target - joint_lower
                upper_margin = joint_upper - joint_target
                finite_actual = np.isfinite(joint_actual)
                finite_target = np.isfinite(joint_target)
                below_lower = joint_target < joint_lower
                above_upper = joint_target > joint_upper
                delta_violation = abs_joint_delta > MAX_JOINT_STEP_RAD

                max_index = int(np.nanargmax(abs_joint_delta)) if np.isfinite(abs_joint_delta).any() else None
                max_delta = float(abs_joint_delta[max_index]) if max_index is not None else None
                per_joint = []
                for local_index, dof_index in enumerate(indices):
                    name_for_joint = str(JOINT_NAMES[int(dof_index)])
                    per_joint.append(
                        {
                            "name": name_for_joint,
                            "index": int(dof_index),
                            "actual": finite_float(joint_actual[local_index]),
                            "target": finite_float(joint_target[local_index]),
                            "delta": finite_float(joint_delta[local_index]),
                            "abs_delta": finite_float(abs_joint_delta[local_index]),
                            "lower": finite_float(joint_lower[local_index]),
                            "upper": finite_float(joint_upper[local_index]),
                            "lower_margin": finite_float(lower_margin[local_index]),
                            "upper_margin": finite_float(upper_margin[local_index]),
                            "below_lower": bool(below_lower[local_index]),
                            "above_upper": bool(above_upper[local_index]),
                            "delta_violation": bool(delta_violation[local_index]),
                            "finite_actual": bool(finite_actual[local_index]),
                            "finite_target": bool(finite_target[local_index]),
                            "finite": bool(finite_actual[local_index] and finite_target[local_index]),
                        }
                    )

                actual_tool_position, actual_tool_rotation, actual_tool_quaternion = current_tool()
                pink_record = {
                    "stage": name,
                    "control_step": index,
                    "solve_status": solve_status,
                    "reset_status": "SUCCESS",
                    "pink_target_finite": bool(finite_target.all()),
                    "raw_pink_joint_target": [finite_float(value) for value in joint_target],
                    "joint_indices": indices.tolist(),
                    "target_eef_position_xyz_m": target_tool_position.tolist(),
                    "target_eef_rotation_matrix": target_tool_rotation.tolist(),
                    "current_eef_position_xyz_m": actual_tool_position.tolist(),
                    "current_eef_quaternion_wxyz": actual_tool_quaternion.tolist(),
                    "current_eef_position_error_m": float(
                        np.linalg.norm(target_tool_position - actual_tool_position)
                    ),
                    "current_eef_orientation_error_rad": float(
                        np.linalg.norm(rotation_error_axis_angle(target_tool_rotation, actual_tool_rotation))
                    ),
                }
                pink_records.append(pink_record)

                violations = []
                nonfinite_rows = [row for row in per_joint if not row["finite_target"]]
                delta_rows = [row for row in per_joint if row["delta_violation"]]
                lower_rows = [row for row in per_joint if row["below_lower"]]
                upper_rows = [row for row in per_joint if row["above_upper"]]
                if nonfinite_rows:
                    violations.append({"code": "NONFINITE_JOINT_TARGET", "joints": nonfinite_rows})
                if delta_rows:
                    violations.append(
                        {
                            "code": "JOINT_DELTA_LIMIT",
                            "threshold_rad": MAX_JOINT_STEP_RAD,
                            "joints": delta_rows,
                        }
                    )
                if lower_rows:
                    violations.append({"code": "JOINT_LOWER_LIMIT", "joints": lower_rows})
                if upper_rows:
                    violations.append({"code": "JOINT_UPPER_LIMIT", "joints": upper_rows})

                if len(violations) > 1:
                    reason_code = "MULTIPLE_SAFETY_VIOLATIONS"
                elif len(violations) == 1:
                    reason_code = violations[0]["code"]
                else:
                    reason_code = "PASS"

                telemetry = {
                    "stage": name,
                    "control_step": index,
                    "original_stage_steps": original_steps,
                    "joint_actual": [finite_float(value) for value in joint_actual],
                    "joint_target": [finite_float(value) for value in joint_target],
                    "joint_delta": [finite_float(value) for value in joint_delta],
                    "abs_joint_delta": [finite_float(value) for value in abs_joint_delta],
                    "max_abs_joint_delta": finite_float(max_delta) if max_delta is not None else None,
                    "max_delta_joint_name": JOINT_NAMES[int(indices[max_index])] if max_index is not None else None,
                    "max_delta_joint_index": int(indices[max_index]) if max_index is not None else None,
                    "joint_lower_limits": [finite_float(value) for value in joint_lower],
                    "joint_upper_limits": [finite_float(value) for value in joint_upper],
                    "lower_margin": [finite_float(value) for value in lower_margin],
                    "upper_margin": [finite_float(value) for value in upper_margin],
                    "finite_joint_actual": bool(finite_actual.all()),
                    "finite_joint_target": bool(finite_target.all()),
                    "per_joint": per_joint,
                    "reason_code": reason_code,
                    "violations": violations,
                    "pink_solve_status": solve_status,
                    "target_eef_pose": {
                        "position_xyz_m": target_tool_position.tolist(),
                        "rotation_matrix": target_tool_rotation.tolist(),
                    },
                    "current_eef_pose": {
                        "position_xyz_m": actual_tool_position.tolist(),
                        "quaternion_wxyz": actual_tool_quaternion.tolist(),
                    },
                }
                telemetry_records.append(telemetry)
                persist_history()
                if name == "descent" and index == 0:
                    atomic_json(output / "descent_step0.json", telemetry)

                if violations:
                    trigger_rows = [row for group in violations for row in group["joints"]]
                    final_decision = {
                        "decision": "REJECT",
                        "reason_code": reason_code,
                        "stage": name,
                        "control_step": index,
                        "trigger_joint": [row["name"] for row in trigger_rows],
                        "trigger_value": [
                            {
                                "joint": row["name"],
                                "target": row["target"],
                                "delta": row["delta"],
                                "abs_delta": row["abs_delta"],
                            }
                            for row in trigger_rows
                        ],
                        "threshold_or_limit": {
                            "max_joint_step_rad": MAX_JOINT_STEP_RAD,
                            "lower": [row["lower"] for row in trigger_rows],
                            "upper": [row["upper"] for row in trigger_rows],
                        },
                        "all_violations": violations,
                    }
                    atomic_json(output / "safety_decision.json", final_decision)
                    raise DiagnosticSafetyStop(reason_code)

                robot.set_dof_position_targets(joint_target.astype(np.float32), dof_indices=indices)
                robot.set_dof_position_targets(
                    np.array([finger_target, finger_target], dtype=np.float32),
                    dof_indices=np.array([7, 8]),
                )
                world.step(render=index % 4 == 0)

        for _ in range(60):
            world.step(render=True)
        robot.set_dof_position_targets(np.array([0.04, 0.04], dtype=np.float32), dof_indices=np.array([7, 8]))
        for _ in range(10):
            world.step(render=True)

        execute_stage(
            "approach",
            pre_grasp_position,
            TOP_DOWN_TOOL_ROTATION,
            STAGE_STEPS["approach"],
            STAGE_STEPS["approach"],
            0.04,
        )
        log_lines.append("Pre-grasp approach completed without a safety rejection.")
        execute_stage(
            "descent",
            grasp_position,
            TOP_DOWN_TOOL_ROTATION,
            STAGE_STEPS["descent"],
            MAX_DIAGNOSTIC_DESCENT_STEPS,
            0.04,
        )
        outcome = "NO_SAFETY_STOP_WITHIN_DIAGNOSTIC_WINDOW"
        final_decision = {
            "decision": "ACTIVE_DIAGNOSTIC_STOP",
            "reason_code": "PASS_WITHIN_DIAGNOSTIC_WINDOW",
            "stage": "descent",
            "last_control_step": descent_step_reached,
            "diagnostic_window_steps": MAX_DIAGNOSTIC_DESCENT_STEPS,
        }
        atomic_json(output / "safety_decision.json", final_decision)
        log_lines.append("No safety rejection in the first three descent steps; stopped by diagnostic protocol.")
    except DiagnosticSafetyStop as exc:
        outcome = "SAFETY_STOP_LOCALIZED"
        log_lines.append(f"Safety rejection captured: {exc}")
    except Exception:
        outcome = "DIAGNOSTIC_ERROR"
        (output / "exception.txt").write_text(traceback.format_exc(), encoding="utf-8")
        log_lines.append("Unexpected diagnostic error; see exception.txt.")
        raise
    finally:
        runtime_sec = time.monotonic() - started
        run_status = {
            "phase": "Phase 3 / Step 7C.2",
            "diagnostic": True,
            "counted": False,
            "completed": outcome in {
                "SAFETY_STOP_LOCALIZED",
                "NO_SAFETY_STOP_WITHIN_DIAGNOSTIC_WINDOW",
            },
            "outcome": outcome,
            "pre_grasp_completed": any(
                record["stage"] == "approach" and record["control_step"] == STAGE_STEPS["approach"] - 1
                for record in telemetry_records
            ),
            "descent_entered": descent_entered,
            "descent_step_reached": descent_step_reached,
            "pink_target_finite": (
                next(
                    (
                        record["pink_target_finite"]
                        for record in reversed(pink_records)
                        if record["stage"] == "descent"
                    ),
                    None,
                )
            ),
            "safety_reason_code": final_decision["reason_code"] if final_decision else None,
            "runtime_sec": runtime_sec,
            "pi05_called": False,
            "predict_action_chunk_called": False,
            "training": False,
            "step6_rerun": False,
            "formal_trial_added": False,
            "formal_results_modified": False,
            "physics_changed": False,
            "safety_threshold_changed": False,
        }
        atomic_json(output / "run_status.json", run_status)
        summary_lines = [
            "# Phase 3 / Step 7C.2 Tomato Safety Telemetry Diagnostic",
            "",
            "- Trial: DIAGNOSTIC / NOT COUNTED",
            f"- Outcome: `{outcome}`",
            f"- Pre-grasp completed: `{run_status['pre_grasp_completed']}`",
            f"- Descent entered: `{descent_entered}`",
            f"- Descent step reached: `{descent_step_reached}`",
            f"- PINK target finite: `{run_status['pink_target_finite']}`",
            f"- Safety reason: `{run_status['safety_reason_code']}`",
            f"- Joint-delta threshold: `{MAX_JOINT_STEP_RAD} rad` (unchanged)",
            "- Pi0.5 / predict_action_chunk / training / Step 6 rerun: not used",
            "- Physics, controller, target, orientation and Safety thresholds: unchanged",
        ]
        (output / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
        log_lines.append(f"Runtime: {runtime_sec:.6f} sec")
        (output / "run.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        app.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
