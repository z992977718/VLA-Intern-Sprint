# Phase 3 / Step 6 实验总结

## 结论

**Experimental Pipeline：PASS。Policy Task Result：0/3。Task Transfer：FAIL。**

本实验把 Phase 1 的同一 LIBERO 语义任务重建到 Isaac Sim，使用冻结的 2k Pi0.5 checkpoint，不训练、不 LoRA、不改模型。三个固定 initial state 均完成严格 100-cycle、K=1 闭环，管线无异常、无 OOM，但两个目标物体均未移动，任务没有成功。

| Episode | Initial state | 成功 | Cycles | 终止 | Wall time |
| --- | ---: | ---: | ---: | --- | ---: |
| 00 | 0 | 否 | 100 | HORIZON_REACHED | 202.552 s |
| 01 | 1 | 否 | 100 | HORIZON_REACHED | 193.751 s |
| 02 | 2 | 否 | 100 | HORIZON_REACHED | 197.332 s |

## 协议与性能

- Instruction：`put both the alphabet soup and the tomato sauce in the basket`
- Checkpoint：`002000/pretrained_model`
- 每 cycle：fresh observation → 一次 `predict_action_chunk` → 50×7 → 只执行 index 0 → Safety → PINK → 新 observation。
- 推理：300 次；mean 182.876 ms，median 181.603 ms，p95 184.141 ms；每回合跳过前 10 次后的 steady-state mean 181.916 ms。
- Action Adapter：mean 0.229 ms，p95 0.251 ms。
- PINK forward：每 cycle mean 1.982 ms，p95 2.125 ms。
- 可测 Observation→action target（inference + adapter）：mean 183.105 ms；不把图像采集、文件握手或运动完成伪装进该指标。
- Torch peak allocated/reserved：9,522,268,160 / 9,877,585,920 bytes（约 8.87 / 9.20 GiB）。
- `nvidia-smi` 全局峰值：13,059 MiB；OOM：NO。

## 失败分类

- Observed：机械臂向桌面任务区与篮子附近连续运动；三个 episode 中两个目标罐位移均为 0，没有可观察的有效接近后接触、抓取、运输或放置。
- Categories：failed approach、failed grasp、horizon reached。
- Possible explanations：视觉/相机域差异、状态分布偏移、action/control 差异和 gripper/physics 差异；均为 hypothesis，不是已证明的模型内部原因。

## 证据

- 对照图：`assets/images/phase3_step6_libero_vs_isaac.png`
- 视频：`assets/videos/phase3_step6_ep00.mp4`、`ep01.mp4`、`ep02.mp4`
- 每轮完整输入、action chunk、动作、轨迹、成功判定和延迟：`episode_00/`、`episode_01/`、`episode_02/`
- 完整哈希清单：`artifact_manifest.json`

本结果不声称 unseen-task generalization、zero-shot new-task、open-world generalization 或 sim-to-real。
