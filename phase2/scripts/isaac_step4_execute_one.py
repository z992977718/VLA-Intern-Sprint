#!/usr/bin/env python3
"""执行且只执行 Step 4 已审计的一个 VLA action。"""

from __future__ import annotations

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

from action_adapter_step4 import matrix_to_quaternion_wxyz, rotation_error_axis_angle

RESULT = Path(os.environ.get("PHASE2_STEP4_RESULT", "/root/autodl-tmp/VLA-Intern-Sprint/results/phase2_step4"))
ASSET = Path(os.environ.get("PHASE2_STEP4_ASSET", "/root/autodl-tmp/VLA-Intern-Sprint/assets"))
ARM = [f"panda_joint{i}" for i in range(1, 8)]
FINGERS = ["panda_finger_joint1", "panda_finger_joint2"]
DT = 1.0 / 60.0


def main() -> None:
    app = SimulationApp({"headless": True, "renderer": "RaytracedLighting"})
    try:
        import warp as wp
        import isaacsim.robot_motion.experimental.motion_generation as mg
        from pxr import Usd, UsdGeom
        from isaacsim.core.api import World
        from isaacsim.core.experimental.prims import Articulation
        from isaacsim.core.experimental.utils.stage import add_reference_to_stage
        from isaacsim.core.utils.extensions import enable_extension
        from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera
        from isaacsim.storage.native import get_assets_root_path

        enable_extension("isaacsim.robot_motion.pink")
        for _ in range(10): app.update()
        from isaacsim.robot_motion.pink import PinkIKController, load_pink_supported_robot

        bounded = json.loads((RESULT / "vla_action_bounded.json").read_text(encoding="utf-8"))
        joint_snapshot = json.loads((RESULT / "joint_state.json").read_text(encoding="utf-8"))
        position_by_name = joint_snapshot["position_by_name"]
        q0 = np.array([position_by_name[n] for n in ARM + FINGERS], dtype=np.float32)
        if not np.isfinite(q0).all(): raise RuntimeError("初始关节状态含 NaN/Inf")

        world = World(stage_units_in_meters=1.0, physics_dt=DT, rendering_dt=DT)
        world.scene.add_default_ground_plane()
        add_reference_to_stage(f"{get_assets_root_path()}/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd", "/panda")
        articulation = Articulation("/panda")
        for _ in range(40): app.update()
        world.reset(); world.play()
        for _ in range(10): world.step(render=True)
        names = list(articulation.dof_names)
        if names != ARM + FINGERS: raise RuntimeError(f"意外 DOF: {names}")
        articulation.set_dof_positions(q0); articulation.set_dof_position_targets(q0)

        camera_position = np.array([1.35, 1.35, 1.15], dtype=np.float32)
        # 与 Step 2/3 相同外部相机姿态。
        from isaac_franka_camera_ros2 import look_at_quaternion
        camera = RtxCamera(path="/World/ExternalCamera", tick_rate=10.0, positions=camera_position,
                           orientations=look_at_quaternion(camera_position, np.array([0.0, 0.0, 0.45])))
        sensor = CameraSensor(camera, resolution=(256, 256), annotators=["rgb"])
        app.update()
        for _ in range(120): world.step(render=True)

        hand = next(p for p in world.stage.Traverse() if p.GetName() == "panda_hand")
        def pose():
            t = UsdGeom.Xformable(hand).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            p = np.array(t.ExtractTranslation(), float); q = t.ExtractRotationQuat(); im = q.GetImaginary()
            qwxyz = np.array([q.GetReal(), im[0], im[1], im[2]], float); qwxyz /= np.linalg.norm(qwxyz)
            w,x,y,z=qwxyz
            r=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                        [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                        [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
            return p,r,qwxyz
        def rgb():
            data,_=sensor.get_data("rgb"); arr=data.numpy()[0] if data.numpy().ndim==4 else data.numpy()
            return np.asarray(arr[...,:3], dtype=np.uint8)

        before_p,before_r,before_q=pose()
        expected=np.asarray(json.loads((RESULT/"eef_pose.json").read_text())["position_xyz_m"])
        if np.linalg.norm(before_p-expected)>0.005: raise RuntimeError("执行初态与 Observation EEF 相差超过 5 mm")
        target_p=np.asarray(bounded["target_position_xyz_m"],float)
        target_r=np.asarray(bounded["target_orientation_matrix"],float)
        workspace_min=np.asarray(bounded["safety_config"]["workspace_min_xyz_m"])
        workspace_max=np.asarray(bounded["safety_config"]["workspace_max_xyz_m"])
        if np.any(target_p<workspace_min) or np.any(target_p>workspace_max): raise RuntimeError("workspace 拒绝")
        Image.fromarray(rgb()).save(ASSET/"images"/"phase2_step4_before.png")

        frames=RESULT/"video_frames"; frames.mkdir(parents=True,exist_ok=True)
        frame_index=0
        def capture():
            nonlocal frame_index
            Image.fromarray(rgb()).save(frames/f"frame_{frame_index:04d}.png"); frame_index+=1
        for i in range(60):
            world.step(render=True)
            if i%6==0: capture()

        pink=load_pink_supported_robot("franka")
        controller=PinkIKController(pink_robot=pink,robot_joint_space=names,robot_site_space=["panda_hand"],
            tool_frame="panda_hand",position_cost=5.0,orientation_cost=0.05,posture_cost=5e-3,solver="osqp",dt=DT)
        lower_raw,upper_raw=articulation.get_dof_limits(); lower=lower_raw.numpy()[0]; upper=upper_raw.numpy()[0]
        def estimated(): return mg.RobotState(joints=mg.JointState.from_name(robot_joint_space=names,
            positions=(names,articulation.get_dof_positions()),velocities=(names,articulation.get_dof_velocities())))
        target_positions=wp.from_numpy(np.asarray([target_p],np.float32),dtype=wp.float32,device="cpu")
        target_orientations=wp.from_numpy(np.asarray([matrix_to_quaternion_wxyz(target_r)],np.float32),dtype=wp.float32,device="cpu")
        setpoint=mg.RobotState(sites=mg.SpatialState.from_name(spatial_space=["panda_hand"],
            positions=(["panda_hand"],target_positions),orientations=(["panda_hand"],target_orientations)))
        if not controller.reset(estimated(),setpoint,0.0): raise RuntimeError("PINK reset 失败")
        latencies=[]; last_target=None; movement_latency=None; wall_start=time.perf_counter()
        for i in range(180):
            start=time.perf_counter(); desired=controller.forward(estimated(),setpoint,i*DT); latencies.append((time.perf_counter()-start)*1000)
            if desired is None or desired.joints.positions is None: raise RuntimeError("PINK forward 失败")
            jt=desired.joints.positions.numpy().astype(float); indices=desired.joints.position_indices.numpy().astype(int)
            current=articulation.get_dof_positions().numpy()[0]
            if not np.isfinite(jt).all(): raise RuntimeError("joint target 非有限")
            if np.max(np.abs(jt-current[indices]))>bounded["safety_config"]["max_joint_step_rad"]: raise RuntimeError("joint step 拒绝")
            if np.any(jt<lower[indices]) or np.any(jt>upper[indices]): raise RuntimeError("joint limit 拒绝")
            articulation.set_dof_position_targets(jt.astype(np.float32),dof_indices=indices); last_target=jt
            if i==0:
                g=float(bounded["gripper_command"]); finger_target=0.0 if g>0.1 else (0.04 if g<-0.1 else float(np.mean(q0[7:])))
                articulation.set_dof_position_targets(np.array([finger_target,finger_target],np.float32),dof_indices=np.array([7,8]))
            world.step(render=True)
            now_p,_,_=pose()
            if movement_latency is None and np.linalg.norm(now_p-before_p)>0.001: movement_latency=(time.perf_counter()-wall_start)*1000
            if i%3==0: capture()
        for i in range(120):
            world.step(render=True)
            if i%6==0: capture()
        after_p,after_r,after_q=pose(); Image.fromarray(rgb()).save(ASSET/"images"/"phase2_step4_after.png")
        joint_actual=articulation.get_dof_positions().numpy()[0]
        before={"eef_position_xyz_m":before_p.tolist(),"eef_quaternion_wxyz":before_q.tolist(),"joint_positions":q0.tolist()}
        after={"eef_position_xyz_m":after_p.tolist(),"eef_quaternion_wxyz":after_q.tolist(),"joint_positions":joint_actual.tolist()}
        error={"commanded_eef_delta_m":(target_p-before_p).tolist(),"actual_eef_delta_m":(after_p-before_p).tolist(),
               "target_position_error_m":float(np.linalg.norm(target_p-after_p)),
               "target_orientation_error_rad":float(np.linalg.norm(rotation_error_axis_angle(target_r,after_r))),
               "robot_moved":bool(np.linalg.norm(after_p-before_p)>0.001)}
        (RESULT/"before_state.json").write_text(json.dumps(before,indent=2)); (RESULT/"after_state.json").write_text(json.dumps(after,indent=2))
        (RESULT/"joint_target.json").write_text(json.dumps({
            "controller_joint_order": names,
            "last_controller_joint_target": last_target.tolist(),
            "arm_joint_target": last_target[:7].tolist(),
            "finger_joint_target": last_target[7:].tolist(),
            "actual_all_joints": joint_actual.tolist(),
        }, indent=2))
        (RESULT/"execution_error.json").write_text(json.dumps(error,indent=2))
        (RESULT/"controller_metrics.json").write_text(json.dumps({"mean_ms":float(np.mean(latencies)),"p95_ms":float(np.percentile(latencies,95)),
            "command_to_movement_ms":movement_latency,"frames":frame_index,"oom":False},indent=2))
        print(json.dumps(error),flush=True)
        if not error["robot_moved"]: raise SystemExit(2)
    except Exception:
        (RESULT/"execution_exception.txt").write_text(traceback.format_exc(),encoding="utf-8"); raise
    finally: app.close()


if __name__=="__main__": main()
