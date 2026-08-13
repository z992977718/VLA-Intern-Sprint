#!/usr/bin/env python3
"""持久加载 Pi0.5；每个 cycle 对新 Observation 只推理一次。"""
from __future__ import annotations
import argparse, copy, json, time
from pathlib import Path
import numpy as np
import torch
from lerobot.configs.policies import PreTrainedConfig
from lerobot.envs.factory import make_env_config
from lerobot.policies.factory import make_policy, make_pre_post_processors
from action_adapter_step4 import SafetyConfig, adapt_libero_action
from policy_input_adapter import build_policy_input
from run_pi05_step4_once import quat_wxyz_to_matrix

def atomic(path: Path, data: dict):
    tmp=path.with_suffix(path.suffix+".tmp");tmp.write_text(json.dumps(data,indent=2),encoding="utf-8");tmp.replace(path)

def main():
    p=argparse.ArgumentParser();p.add_argument("--checkpoint",type=Path,required=True);p.add_argument("--result-dir",type=Path,required=True);p.add_argument("--cycles",type=int,default=5);p.add_argument("--language",default="move the robot arm");a=p.parse_args()
    if a.cycles!=5:raise ValueError("MAX_CYCLES 必须为 5")
    result=a.result_dir.resolve();result.mkdir(parents=True,exist_ok=True)
    env=make_env_config("libero",task="libero_10",task_ids=[0],observation_height=256,observation_width=256,init_states=True,hard_reset=True,control_mode="relative",max_parallel_tasks=1)
    cfg=PreTrainedConfig.from_pretrained(str(a.checkpoint));cfg.pretrained_path=a.checkpoint;cfg.device="cuda";cfg.dtype="bfloat16";cfg.use_amp=False
    t=time.perf_counter();policy=make_policy(cfg=cfg,env_cfg=env,rename_map={});policy.eval()
    pre,post=make_pre_post_processors(policy_cfg=cfg,pretrained_path=str(a.checkpoint),preprocessor_overrides={"device_processor":{"device":"cuda"},"rename_observations_processor":{"rename_map":{}}})
    torch.cuda.synchronize();atomic(result/"policy_ready.json",{"ready":True,"model_load_sec":time.perf_counter()-t,"max_cycles":5})
    torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats();safety=SafetyConfig();records=[]
    for i in range(5):
        cycle=result/f"cycle_{i:02d}";ready=cycle/"observation_ready.json";deadline=time.monotonic()+90
        while not ready.is_file():
            if (result/"stop").exists():raise RuntimeError("stop")
            if time.monotonic()>deadline:raise TimeoutError(f"cycle {i} observation timeout")
            time.sleep(.02)
        meta=json.loads(ready.read_text());obs,sample=build_policy_input(cycle,a.language)
        torch.cuda.synchronize();t=time.perf_counter()
        with torch.inference_mode():normalized=policy.predict_action_chunk(pre(copy.deepcopy(obs)))
        torch.cuda.synchronize();infer=(time.perf_counter()-t)*1000;chunk=post(normalized).detach().cpu().numpy()
        if chunk.shape!=(1,50,7) or not np.isfinite(chunk).all():raise RuntimeError("invalid action chunk")
        np.save(cycle/"action_chunk.npy",chunk[0]);first=chunk[0,0].astype(float);eef=json.loads((cycle/"eef_pose.json").read_text())
        t=time.perf_counter();bounded=adapt_libero_action(first,np.asarray(eef["position_xyz_m"]),quat_wxyz_to_matrix(np.asarray(eef["quaternion_wxyz"])),safety);adapter=(time.perf_counter()-t)*1000
        response={"cycle_index":i,"observation_timestamp":meta["observation_timestamp"],"inference_call_index":i,"predict_action_chunk_calls_this_cycle":1,"chunk_shape":list(chunk.shape),"chunk_finite":True,"raw_first_action":first.tolist(),"bounded":bounded,"inference_latency_ms":infer,"adapter_latency_ms":adapter,"torch_allocated_bytes":torch.cuda.memory_allocated(),"torch_reserved_bytes":torch.cuda.memory_reserved(),"remaining_49_actions_authorized":False}
        atomic(cycle/"policy_response.json",response);records.append(response);done=cycle/"execution_complete.json";deadline=time.monotonic()+90
        while not done.is_file():
            if (result/"stop").exists():raise RuntimeError("stop")
            if time.monotonic()>deadline:raise TimeoutError(f"cycle {i} execution timeout")
            time.sleep(.02)
    atomic(result/"policy_complete.json",{"cycles":5,"real_inference_calls":5,"inference_latency_ms":[r["inference_latency_ms"] for r in records],"adapter_latency_ms":[r["adapter_latency_ms"] for r in records],"torch_peak_allocated_bytes":torch.cuda.max_memory_allocated(),"torch_peak_reserved_bytes":torch.cuda.max_memory_reserved(),"oom":False})
if __name__=="__main__":main()
