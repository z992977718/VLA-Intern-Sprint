# Phase 3 / Step 7D：修复后 Pi0.5 单回合诊断

## 1. 阶段性质

- 类型：`DIAGNOSTIC / NOT COUNTED`
- Episode：严格 1 次
- Initial state：Step 6 fixed initial state 0
- Horizon：100 cycles
- Receding horizon：`K=1`
- 每轮均重新采集 observation、真实调用一次 Pi0.5，并且只执行 `action_chunk[0]`
- 本结果不是新 benchmark，不计入成功率；没有补跑、筛 seed 或运行 state 1/2。

## 2. 冻结配置

- Checkpoint：`002000/pretrained_model`
- `model.safetensors` SHA-256：`590c83ba6061fbfeb887d675deb9b173bbe23f65722c6b38ce242825ffbac631`
- `config.json` SHA-256：`eab7fc62be9d58ad679d12d15223b18e01a604a775fad089f5dc96d46cc58df7`
- 权重修改：否
- 场景、物体、篮子、桌子、两路相机、指令、state 0 和 success detector：复用 Step 6
- Position State Mapping：原生 USD `/World/Robot/panda_hand/tool_center`
- Gripper State Mapping：Isaac `[finger1, finger2]` → LIBERO-compatible `[finger1, -finger2]`
- PINK：7D arm-only，夹爪独立控制
- Safety：Step 7C.3 floating-point-safe joint limit
- 新增 orientation fix：否
- 新增 timestamp fix：否

## 3. Step 6 BEFORE 与 Step 7D AFTER

| 指标 | Step 6 BEFORE | Step 7D AFTER | 变化 |
|---|---:|---:|---:|
| Episode 结果 | HORIZON_REACHED | HORIZON_REACHED | 无任务成功变化 |
| Cycles | 100 | 100 | 0 |
| EEF endpoint path length | 0.944371 m | 0.779725 m | -0.164647 m |
| Min distance to alphabet | 0.258149 m | 0.263074 m | +0.004925 m |
| Min distance to tomato | 0.193477 m | 0.201323 m | +0.007846 m |
| Alphabet max displacement | 0 m | 0 m | 0 |
| Tomato max displacement | 0 m | 0 m | 0 |
| Close-command cycles | 83 | 64 | -19 |
| Safety violations | 0 | 0 | 0 |
| IK failures | 0 | 0 | 0 |
| Mean inference latency | 185.203 ms | 259.769 ms | +74.566 ms |
| Median inference latency | 181.429 ms | 237.058 ms | +55.629 ms |
| P95 inference latency | 184.701 ms | 322.760 ms | +138.059 ms |

距离比较必须带上口径说明：Step 6 BEFORE 使用其当时记录的 `panda_hand + fixed offset`；Step 7D AFTER 使用修复后的原生 USD `tool_center`。位置参考本身就是本轮被审计的修复，不能把两个数值当作完全相同测量坐标系下的独立重复试验。

## 4. AFTER 行为证据

- Min tool-center-to-alphabet：`0.263074 m`，cycle 0
- Min tool-center-to-tomato：`0.201323 m`，cycle 17
- Alphabet 最大/最终位移：`0 / 0 m`
- Tomato 最大/最终位移：`0 / 0 m`
- OBJECT_MOTION_OBSERVED：两物体均 `NO`
- Close command：64 cycles；Open command：36 cycles；Hold：0 cycles
- 最接近物体的 close 发生在 cycle 19，但距离 tomato 仍为 `0.201665 m`，因此分类为 `CLOSE_FAR_FROM_OBJECT`，不是 plausible grasp attempt。
- Action clipping：99/100。这里表示动作适配器按既有边界裁剪，并不等于 Safety violation。
- Safety intervention：0
- PINK failure：0
- Finger configuration-limit regression：未出现
- 本回合实测 image-state max skew：`0.001081 s`；没有修改 timestamp 实现，既有“历史测得最高约 0.15 s”的限制仍保留，不能声称已修复。

行为分类：`NO_CLEAR_IMPROVEMENT`。

失败标签：`FAILED_APPROACH`、`FAILED_GRASP`、`HORIZON_REACHED`。这些是行为层证据，不是对 Pi0.5/VLM/attention、orientation、timestamp 或 domain gap 的内部根因定位。

## 5. Runtime / GPU

- RTX 5090，总显存：32607 MiB
- Torch peak allocated：`9,522,268,160 bytes`（约 8.87 GiB）
- Torch peak reserved：`9,877,585,920 bytes`（约 9.20 GiB）
- `nvidia-smi` peak used：`12955 MiB`
- 最终 GPU：`0 MiB / 0%`
- OOM：否
- Isaac runtime：`253.653 s`

策略完成 100 次真实 inference。最后一轮出现文件握手竞态：策略在读到 cycle 99 的 `execution_complete.json` 后、Isaac 原子写出顶层 `episode_complete.json` 前执行了最终检查，因此原始 policy exit code 为 1。证据显示 100 个 policy response、100 个已执行 cycle、Isaac exit code 0、完整 episode completion 且无 OOM；原始 `policy_complete.json` 保留不改，独立记录在 `policy_handshake_reconciliation.json`。该竞态不需要也不允许重跑 episode；代码只对未来运行增加 5 秒有界握手等待。

## 6. 结论与边界

- Step 7D：`PASS`，含义仅为单次授权诊断完整执行、证据保存和运行层无关键回归。
- Diagnostic task：`FAILURE / HORIZON_REACHED`
- Did alphabet move：`NO`
- Did tomato move：`NO`
- Plausible grasp attempt：`NO`
- Major confirmed robot-side blockers cleared：`YES`
- 能否把 Step 6 的 0/3 仅归因于这些 robot-side bug：`NO`
- 推荐项目决策：`FREEZE_FRANKA_ISAAC_MAINLINE`
- 是否继续 Franka benchmark episode：`NO`
- 是否自动开始训练 / LoRA / RL：`NO`

仍保留的已知限制：orientation mapping `UNRESOLVED`、历史 image-state skew 最高约 0.15 s、跨模拟器视觉/域差异、controller/embodiment 差异。

## 7. 产物

- 完整远程目录：`/root/autodl-tmp/VLA-Intern-Sprint/results/phase3_step7/pi05_postfix_diagnostic/`
- 本地核心结果：`results/phase3_step7/pi05_postfix_diagnostic/`
- 视频：`assets/videos/phase3_step7_pi05_postfix_diagnostic_state0.mp4`
- 视频 SHA-256：`f50ee2a688ac13fdc9727504914ec31a5b228c636dd428fa8ed3bbd628a64197`
- 截图：start、closest-to-alphabet、closest-to-tomato、closest-close-attempt-far-from-objects、final
- Strongest grasp attempt：不存在，索引为 `null`，没有伪造截图。

远程保留 100 个逐-cycle 目录、100 个 cycle JSON 和 2001 张原始视频帧；本地保存聚合 `cycle_telemetry.json`、核心日志、报告、截图与 MP4，未覆盖任何 Step 6 或 Step 7C 资产。
