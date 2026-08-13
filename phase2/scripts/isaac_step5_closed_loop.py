#!/usr/bin/env python3
"""同一 Isaac 场景中的五轮 receding-horizon VLA runtime。"""
from __future__ import annotations
import json,os,time,traceback
from pathlib import Path
import numpy as np
from PIL import Image
os.environ.setdefault("OMNI_KIT_ACCEPT_EULA","YES")
from isaacsim import SimulationApp
from action_adapter_step4 import matrix_to_quaternion_wxyz,rotation_error_axis_angle
RESULT=Path(os.environ.get("PHASE2_STEP5_RESULT","/root/autodl-tmp/VLA-Intern-Sprint/results/phase2_step5"));ASSETS=Path(os.environ.get("PHASE2_STEP5_ASSETS","/root/autodl-tmp/VLA-Intern-Sprint/assets"))
ARM=[f"panda_joint{i}" for i in range(1,8)];FINGERS=["panda_finger_joint1","panda_finger_joint2"];NAMES=ARM+FINGERS
Q0=np.array([.012,-.5686,0,-2.8109,0,3.0368,.741,0,0],np.float32);DT=1/60;MAX_CYCLES=5;MAX_RUNTIME=300;MAX_TOTAL_EEF=.03;MAX_CUM_JOINT=1.0
def atomic(path,data):
    tmp=path.with_suffix(path.suffix+".tmp");tmp.write_text(json.dumps(data,indent=2),encoding="utf-8");tmp.replace(path)
def main():
    app=SimulationApp({"headless":True,"renderer":"RaytracedLighting"});started=time.monotonic()
    try:
        import warp as wp
        import isaacsim.robot_motion.experimental.motion_generation as mg
        from pxr import Usd,UsdGeom
        from isaacsim.core.api import World
        from isaacsim.core.experimental.prims import Articulation
        from isaacsim.core.experimental.utils.stage import add_reference_to_stage
        from isaacsim.core.utils.extensions import enable_extension
        from isaacsim.sensors.experimental.rtx import CameraSensor,RtxCamera
        from isaacsim.storage.native import get_assets_root_path
        from isaac_franka_camera_ros2 import look_at_quaternion
        enable_extension("isaacsim.robot_motion.pink")
        for _ in range(10):app.update()
        from isaacsim.robot_motion.pink import PinkIKController,load_pink_supported_robot
        world=World(stage_units_in_meters=1,physics_dt=DT,rendering_dt=DT);world.scene.add_default_ground_plane();add_reference_to_stage(f"{get_assets_root_path()}/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd","/panda")
        robot=Articulation("/panda")
        for _ in range(40):app.update()
        world.reset();world.play()
        for _ in range(10):world.step(render=True)
        if list(robot.dof_names)!=NAMES:raise RuntimeError("DOF mismatch")
        robot.set_dof_positions(Q0);robot.set_dof_position_targets(Q0)
        hand=next(p for p in world.stage.Traverse() if p.GetName()=="panda_hand")
        def pose():
            t=UsdGeom.Xformable(hand).ComputeLocalToWorldTransform(Usd.TimeCode.Default());p=np.array(t.ExtractTranslation(),float);q=t.ExtractRotationQuat();im=q.GetImaginary();qw=np.array([q.GetReal(),im[0],im[1],im[2]],float);qw/=np.linalg.norm(qw);w,x,y,z=qw
            r=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
            return p,r,qw
        extp=np.array([1.35,1.35,1.15],np.float32);external=RtxCamera(path="/World/ExternalCamera",tick_rate=10,positions=extp,orientations=look_at_quaternion(extp,np.array([0,0,.45])))
        def wrist_pose():
            p,_,_=pose();eye=p+np.array([-.45,-.65,.45]);return eye,look_at_quaternion(eye,p+np.array([.30,0,-.50]))
        eye,wq=wrist_pose();wrist=RtxCamera(path="/World/WristTrackingCamera",tick_rate=10,positions=eye,orientations=wq)
        es=CameraSensor(external,resolution=(256,256),annotators=["rgb"]);ws=CameraSensor(wrist,resolution=(256,256),annotators=["rgb"]);app.update()
        for _ in range(120):eye,wq=wrist_pose();wrist.set_world_poses(eye,wq);world.step(render=True)
        def rgb(sensor):
            d,_=sensor.get_data("rgb");a=d.numpy();a=a[0] if a.ndim==4 else a;return np.asarray(a[...,:3],np.uint8)
        pink=load_pink_supported_robot("franka");controller=PinkIKController(pink_robot=pink,robot_joint_space=NAMES,robot_site_space=["panda_hand"],tool_frame="panda_hand",position_cost=5.0,orientation_cost=.05,posture_cost=5e-3,solver="osqp",dt=DT)
        lr,ur=robot.get_dof_limits();low=lr.numpy()[0];high=ur.numpy()[0]
        def estimated():return mg.RobotState(joints=mg.JointState.from_name(robot_joint_space=NAMES,positions=(NAMES,robot.get_dof_positions()),velocities=(NAMES,robot.get_dof_velocities())))
        frames=RESULT/"frames";video=RESULT/"video_frames";frames.mkdir(parents=True,exist_ok=True);video.mkdir(parents=True,exist_ok=True);frame_i=0
        def capture():
            nonlocal frame_i
            Image.fromarray(rgb(es)).save(video/f"frame_{frame_i:04d}.png");frame_i+=1
        start_p,start_r,start_q=pose();start_j=robot.get_dof_positions().numpy()[0].copy();prev_j=start_j.copy();cum_joint=0.;records=[]
        atomic(RESULT/"start_state.json",{"eef_position_xyz_m":start_p.tolist(),"eef_quaternion_wxyz":start_q.tolist(),"joints":start_j.tolist()});Image.fromarray(rgb(es)).save(ASSETS/"images"/"phase2_step5_start.png")
        for i in range(MAX_CYCLES):
            if time.monotonic()-started>MAX_RUNTIME:raise TimeoutError("maximum runtime")
            cycle=RESULT/f"cycle_{i:02d}";cycle.mkdir(parents=True,exist_ok=True)
            for _ in range(12):eye,wq=wrist_pose();wrist.set_world_poses(eye,wq);world.step(render=True)
            cts=time.time();ext=rgb(es);wri=rgb(ws);sts=time.time();bp,br,bq=pose();joints=robot.get_dof_positions().numpy()[0];skew=abs(cts-sts)
            if skew>.25:raise RuntimeError("stale observation")
            Image.fromarray(ext).save(cycle/"camera_external.png");Image.fromarray(wri).save(cycle/"camera_wrist.png")
            atomic(cycle/"joint_state.json",{"topic":"Isaac direct articulation state","raw_order":NAMES,"position_by_name":{n:float(v) for n,v in zip(NAMES,joints,strict=True)},"timestamp":sts})
            atomic(cycle/"eef_pose.json",{"timestamp":sts,"source_prim":str(hand.GetPath()),"reference_frame":"/World","position_unit":"meter","position_xyz_m":bp.tolist(),"quaternion_wxyz":bq.tolist(),"quaternion_xyzw":np.roll(bq,-1).tolist()})
            meta={"cycle_index":i,"camera_timestamp":cts,"robot_state_timestamp":sts,"observation_timestamp":max(cts,sts),"image_state_skew_sec":skew,"language":"move the robot arm","fresh_files":True};atomic(cycle/"observation_ready.json",meta)
            wait=time.monotonic();response_file=cycle/"policy_response.json"
            while not response_file.is_file():
                if time.monotonic()-wait>30:raise TimeoutError("inference timeout")
                time.sleep(.01)
            response=json.loads(response_file.read_text());bounded=response["bounded"]
            if response["cycle_index"]!=i or response["observation_timestamp"]!=meta["observation_timestamp"] or response["predict_action_chunk_calls_this_cycle"]!=1:raise RuntimeError("stale policy response")
            tp=np.asarray(bounded["target_position_xyz_m"],float);tr=np.asarray(bounded["target_orientation_matrix"],float)
            if np.linalg.norm(tp-start_p)>MAX_TOTAL_EEF:raise RuntimeError("maximum total EEF displacement")
            wp_p=wp.from_numpy(np.asarray([tp],np.float32),dtype=wp.float32,device="cpu");wp_q=wp.from_numpy(np.asarray([matrix_to_quaternion_wxyz(tr)],np.float32),dtype=wp.float32,device="cpu")
            setpoint=mg.RobotState(sites=mg.SpatialState.from_name(spatial_space=["panda_hand"],positions=(["panda_hand"],wp_p),orientations=(["panda_hand"],wp_q)))
            if not controller.reset(estimated(),setpoint,i):raise RuntimeError("PINK reset")
            cms=[];last=None;cycle_start=time.monotonic()
            for step in range(120):
                t=time.perf_counter();desired=controller.forward(estimated(),setpoint,i+step*DT);cms.append((time.perf_counter()-t)*1000)
                if desired is None or desired.joints.positions is None:raise RuntimeError("PINK failure")
                jt=desired.joints.positions.numpy().astype(float);idx=desired.joints.position_indices.numpy().astype(int);current=robot.get_dof_positions().numpy()[0]
                if not np.isfinite(jt).all() or np.max(np.abs(jt-current[idx]))>.05 or np.any(jt<low[idx]) or np.any(jt>high[idx]):raise RuntimeError("joint safety")
                robot.set_dof_position_targets(jt.astype(np.float32),dof_indices=idx);last=jt
                if step==0:
                    g=float(bounded["gripper_command"]);finger=0 if g>.1 else (.04 if g<-.1 else float(np.mean(current[7:])));robot.set_dof_position_targets(np.array([finger,finger],np.float32),dof_indices=np.array([7,8]))
                eye,wq=wrist_pose();wrist.set_world_poses(eye,wq);world.step(render=True)
                if step%4==0:capture()
            ap,ar,aq=pose();aj=robot.get_dof_positions().numpy()[0];cum_joint+=float(np.linalg.norm(aj[:7]-prev_j[:7]));prev_j=aj.copy()
            if cum_joint>MAX_CUM_JOINT:raise RuntimeError("maximum cumulative joint displacement")
            rec={"cycle_index":i,**meta,"raw_action_chunk_shape":response["chunk_shape"],"raw_first_action":response["raw_first_action"],"bounded_action":bounded["bounded_action"],"eef_before_xyz_m":bp.tolist(),"eef_target_xyz_m":tp.tolist(),"eef_after_xyz_m":ap.tolist(),"actual_eef_delta_m":(ap-bp).tolist(),"position_error_m":float(np.linalg.norm(tp-ap)),"orientation_error_rad":float(np.linalg.norm(rotation_error_axis_angle(tr,ar))),"joint_target":last.tolist(),"gripper_before_m":joints[7:].tolist(),"gripper_after_m":aj[7:].tolist(),"inference_latency_ms":response["inference_latency_ms"],"adapter_latency_ms":response["adapter_latency_ms"],"controller_latency_mean_ms":float(np.mean(cms)),"controller_latency_p95_ms":float(np.percentile(cms,95)),"observation_to_motion_complete_ms":(time.monotonic()-wait)*1000,"eef_distance_from_start_m":float(np.linalg.norm(ap-start_p)),"cumulative_joint_endpoint_displacement_rad":cum_joint,"safety_status":"PASS","action_index_executed":0,"remaining_actions_executed":0}
            atomic(RESULT/f"cycle_{i:02d}.json",rec);atomic(cycle/"execution_complete.json",{"cycle_index":i,"pass":True});records.append(rec)
        ep,er,eq=pose();ej=robot.get_dof_positions().numpy()[0];atomic(RESULT/"end_state.json",{"eef_position_xyz_m":ep.tolist(),"eef_quaternion_wxyz":eq.tolist(),"joints":ej.tolist()});Image.fromarray(rgb(es)).save(ASSETS/"images"/"phase2_step5_end.png")
        atomic(RESULT/"isaac_complete.json",{"cycles_completed":5,"frames":frame_i,"total_eef_displacement_m":float(np.linalg.norm(ep-start_p)),"cumulative_joint_endpoint_displacement_rad":cum_joint,"runtime_sec":time.monotonic()-started})
    except Exception:
        atomic(RESULT/"isaac_failure.json",{"error":traceback.format_exc(),"timestamp":time.time()});(RESULT/"stop").touch();raise
    finally:app.close()
if __name__=="__main__":main()
