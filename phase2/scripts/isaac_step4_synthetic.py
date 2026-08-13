#!/usr/bin/env python3
"""使用 Isaac Sim 6.0.1 官方 PINK 控制器执行 Step 4 合成安全测试。"""

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

from action_adapter_step4 import SafetyConfig, matrix_to_quaternion_wxyz, rotation_error_axis_angle

RESULT = Path(os.environ.get("PHASE2_STEP4_RESULT", "/root/autodl-tmp/VLA-Intern-Sprint/results/phase2_step4"))
ARM = [f"panda_joint{i}" for i in range(1, 8)]
FINGERS = ["panda_finger_joint1", "panda_finger_joint2"]
Q0 = np.array([0.012, -0.568, 0.0, -2.811, 0.0, 3.037, 0.741, 0.035, 0.035], dtype=np.float32)
DT = 1.0 / 60.0


def main() -> None:
    RESULT.mkdir(parents=True, exist_ok=True)
    app = SimulationApp({"headless": True})
    try:
        import isaacsim.robot_motion.experimental.motion_generation as mg
        import warp as wp
        from pxr import Usd, UsdGeom
        from isaacsim.core.api import World
        from isaacsim.core.experimental.prims import Articulation
        from isaacsim.core.experimental.utils.stage import add_reference_to_stage
        from isaacsim.core.utils.extensions import enable_extension
        from isaacsim.storage.native import get_assets_root_path

        enable_extension("isaacsim.robot_motion.pink")
        for _ in range(10):
            app.update()
        from isaacsim.robot_motion.pink import PinkIKController, load_pink_supported_robot

        world = World(stage_units_in_meters=1.0, physics_dt=DT, rendering_dt=DT)
        world.scene.add_default_ground_plane()
        asset = f"{get_assets_root_path()}/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd"
        add_reference_to_stage(asset, "/panda")
        articulation = Articulation("/panda")
        for _ in range(40):
            app.update()
        world.reset()
        world.play()
        for _ in range(10):
            world.step(render=False)

        names = list(articulation.dof_names)
        if names != ARM + FINGERS:
            raise RuntimeError(f"意外的 Franka DOF 顺序: {names}")
        articulation.set_dof_positions(Q0)
        articulation.set_dof_position_targets(Q0)
        for _ in range(90):
            world.step(render=False)

        hand = world.stage.GetPrimAtPath("/panda/panda_hand")
        if not hand.IsValid():
            for prim in world.stage.Traverse():
                if prim.GetName() == "panda_hand":
                    hand = prim
                    break

        def pose() -> tuple[np.ndarray, np.ndarray]:
            transform = UsdGeom.Xformable(hand).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            p = np.array(transform.ExtractTranslation(), dtype=np.float64)
            q = transform.ExtractRotationQuat()
            imag = q.GetImaginary()
            qwxyz = np.array([q.GetReal(), imag[0], imag[1], imag[2]], dtype=np.float64)
            qwxyz /= np.linalg.norm(qwxyz)
            w, x, y, z = qwxyz
            r = np.array([
                [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)],
            ])
            return p, r

        pink = load_pink_supported_robot("franka")
        controller = PinkIKController(
            pink_robot=pink, robot_joint_space=names, robot_site_space=["panda_hand"],
            tool_frame="panda_hand", position_cost=5.0, orientation_cost=0.05,
            posture_cost=5e-3, solver="osqp", dt=DT,
        )
        lower_limits_raw, upper_limits_raw = articulation.get_dof_limits()
        lower_limits = lower_limits_raw.numpy()[0]
        upper_limits = upper_limits_raw.numpy()[0]
        safety = SafetyConfig()
        controller_latencies = []

        def estimated():
            return mg.RobotState(joints=mg.JointState.from_name(
                robot_joint_space=names,
                positions=(names, articulation.get_dof_positions()),
                velocities=(names, articulation.get_dof_velocities()),
            ))

        def move_to(target_p: np.ndarray, target_r: np.ndarray, steps: int = 180) -> dict:
            target_positions = wp.from_numpy(
                np.asarray([target_p], dtype=np.float32), dtype=wp.float32, device="cpu"
            )
            target_orientations = wp.from_numpy(
                np.asarray([matrix_to_quaternion_wxyz(target_r)], dtype=np.float32),
                dtype=wp.float32,
                device="cpu",
            )
            setpoint = mg.RobotState(sites=mg.SpatialState.from_name(
                spatial_space=["panda_hand"],
                positions=(["panda_hand"], target_positions),
                orientations=(["panda_hand"], target_orientations),
            ))
            if not controller.reset(estimated(), setpoint, 0.0):
                raise RuntimeError("PINK reset 失败")
            last_target = None
            for index in range(steps):
                started = time.perf_counter()
                desired = controller.forward(estimated(), setpoint, index * DT)
                controller_latencies.append((time.perf_counter() - started) * 1000.0)
                if desired is None or desired.joints.positions is None:
                    raise RuntimeError("PINK forward 未返回 joint target")
                joint_target = desired.joints.positions.numpy().astype(np.float64)
                indices = desired.joints.position_indices.numpy().astype(int)
                current = articulation.get_dof_positions().numpy()[0]
                if not np.isfinite(joint_target).all():
                    raise RuntimeError("joint target 含 NaN/Inf")
                if np.max(np.abs(joint_target - current[indices])) > safety.max_joint_step_rad:
                    raise RuntimeError("单次 joint target 位移超过安全限制")
                if np.any(joint_target < lower_limits[indices]) or np.any(joint_target > upper_limits[indices]):
                    raise RuntimeError("joint target 超过 USD joint limits")
                articulation.set_dof_position_targets(joint_target.astype(np.float32), dof_indices=indices)
                last_target = joint_target
                world.step(render=False)
            actual_p, actual_r = pose()
            return {
                "joint_target": last_target.tolist(),
                "actual_position_xyz_m": actual_p.tolist(),
                "position_error_m": float(np.linalg.norm(target_p - actual_p)),
                "orientation_error_rad": float(np.linalg.norm(rotation_error_axis_angle(target_r, actual_r))),
            }

        origin_p, origin_r = pose()
        translation_records = []
        for axis in range(3):
            delta = np.zeros(3); delta[axis] = 0.005
            result = move_to(origin_p + delta, origin_r)
            actual_delta = np.asarray(result["actual_position_xyz_m"]) - origin_p
            result.update({"axis": "xyz"[axis], "command_delta_m": delta.tolist(), "actual_delta_m": actual_delta.tolist()})
            result["pass"] = bool(actual_delta[axis] > 0.003 and np.linalg.norm(np.delete(actual_delta, axis)) < 0.003)
            translation_records.append(result)
            move_to(origin_p, origin_r)

        rotation_records = []
        from action_adapter_step4 import axis_angle_to_matrix
        for axis in range(3):
            vector = np.zeros(3); vector[axis] = 0.02
            target_r = axis_angle_to_matrix(vector) @ origin_r
            result = move_to(origin_p, target_r)
            _, actual_r = pose()
            actual_delta = rotation_error_axis_angle(actual_r, origin_r)
            result.update({"axis": "xyz"[axis], "command_axis_angle_rad": vector.tolist(), "actual_axis_angle_rad": actual_delta.tolist()})
            result["pass"] = bool(actual_delta[axis] > 0.01 and np.linalg.norm(np.delete(actual_delta, axis)) < 0.02)
            rotation_records.append(result)
            move_to(origin_p, origin_r)

        frame = {
            "controller": "Isaac Sim 6.0.1 PinkIKController",
            "translation": translation_records,
            "rotation": rotation_records,
            "mapping": "identity axes; LIBERO world/spatial delta -> Isaac /World",
            "validated": all(x["pass"] for x in translation_records + rotation_records),
        }
        (RESULT / "frame_mapping_test.json").write_text(json.dumps(frame, indent=2), encoding="utf-8")

        gripper_records = []
        finger_indices = np.array([names.index(n) for n in FINGERS])
        for label, target in (("OPEN", 0.04), ("CLOSE", 0.0), ("NEUTRAL", 0.02)):
            articulation.set_dof_position_targets(np.array([target, target], np.float32), dof_indices=finger_indices)
            for _ in range(90): world.step(render=False)
            actual = articulation.get_dof_positions().numpy()[0, finger_indices]
            gripper_records.append({"command": label, "target_m": [target, target], "actual_m": actual.tolist(),
                                     "pass": bool(np.max(np.abs(actual-target)) < 0.005)})
        gripper = {"joint_limits_m": np.column_stack((lower_limits[finger_indices], upper_limits[finger_indices])).tolist(), "records": gripper_records,
                   "validated": all(x["pass"] for x in gripper_records)}
        (RESULT / "gripper_mapping_test.json").write_text(json.dumps(gripper, indent=2), encoding="utf-8")

        synthetic = {
            "command": "LIBERO action [0.1,0,0,0,0,0,0] -> +5 mm Isaac /World x",
            "frame_mapping_pass": frame["validated"], "gripper_mapping_pass": gripper["validated"],
            "robot_moved": translation_records[0]["pass"],
            "controller_latency_mean_ms": float(np.mean(controller_latencies)),
            "controller_latency_p95_ms": float(np.percentile(controller_latencies, 95)),
            "pass": bool(frame["validated"] and gripper["validated"]),
        }
        (RESULT / "synthetic_action_test.json").write_text(json.dumps(synthetic, indent=2), encoding="utf-8")
        print(json.dumps(synthetic), flush=True)
        if not synthetic["pass"]:
            raise SystemExit(2)
    except Exception:
        (RESULT / "synthetic_exception.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        app.close()


if __name__ == "__main__":
    main()
