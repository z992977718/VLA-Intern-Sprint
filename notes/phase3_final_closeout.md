# Phase 3 最终收尾：Franka / Isaac 主线冻结

日期：2026-08-13

最终工程决策：

```text
FREEZE_FRANKA_ISAAC_MAINLINE
```

本文件冻结 Phase 1–3 的事实、结论和证据边界。本轮只整理已有结果，没有连接远程 GPU、没有启动 Isaac、Pi0.5、训练、Rollout 或 SO-101 实验，也没有覆盖任何原始实验资产。

## 1. 项目主线

```text
Phase 1: Model
LIBERO / MuJoCo policy learning and evaluation

Phase 2: Runtime + Robot
Isaac Sim / ROS 2 / Franka integration

Phase 3: Evaluation + Failure Analysis
Cross-simulator task rollout and systematic localization
```

项目完成了从模型继续微调、闭环评测、机器人运行时接入，到跨模拟器任务验证和分层故障定位的完整工程链路。各阶段的指标属于不同实验环境，不得相互替换。

## 2. Phase 1：LIBERO / MuJoCo Policy Learning

### 2.1 训练事实

- Policy：LeRobot Pi0.5；
- 起始 checkpoint：`lerobot/pi05_libero_base`；
- 数据集：固定 revision 的完整 40-task `lerobot/libero`；
- 数据规模：1,693 episodes、273,465 frames；
- Suites：Spatial、Object、Goal、LIBERO-10；
- Continued fine-tuning：2,000 steps；
- 已保存 checkpoint：001000、002000。

### 2.2 重点评测

- Suite / task：`libero_10` task 0；
- Instruction：`put both the alphabet soup and the tomato sauce in the basket`；
- 重点 checkpoint：002000；
- 50 个固定 initial states：46 success / 4 failure。

### 2.3 声明边界

`46/50` 是同一指定 LIBERO 任务的固定初态评测结果：

- 不是整个 LIBERO benchmark 的 92% 成功率；
- 不是 Isaac success rate；
- 不是 unseen-task 或 open-world generalization；
- initial states 30–49 只能称为 additional / previously unevaluated fixed initial states，不能称为 training-held-out states。

## 3. Phase 2：Isaac / ROS 2 / Franka Runtime Integration

Phase 2 完成以下运行时组件：

- 两路 RGB 与 robot state 的 Observation Adapter；
- language instruction 注入；
- 使用真实 2k checkpoint 的 Pi0.5 Policy Adapter；
- `[1, 50, 7]` Action Chunk；
- LIBERO-compatible Action Adapter；
- Safety Layer；
- PINK differential IK；
- Franka command / feedback；
- receding-horizon closed loop。

Step 5 使用最保守协议完成 5 个 cycle：每轮重新采集 observation，真实执行一次 `predict_action_chunk`，只执行 `action_chunk[0]`，然后再次采集运动后的 observation。结果为 **Runtime Integration PASS**。

Phase 2 没有建立任务物体和 task-success detector，因此只证明 VLA runtime closed loop 工作，不证明抓取、任务迁移或跨域泛化。

## 4. Phase 3 / Step 6：Cross-simulator Task Evaluation

同一语义任务被重建到 Isaac Sim，并使用 Step 6 固定 initial states 0、1、2 做三次闭环：

| 指标 | 结果 |
| --- | --- |
| Episodes | 3 |
| Max cycles / episode | 100 |
| Action execution horizon | K=1 |
| Task success | 0/3 |
| Termination | 3× `HORIZON_REACHED` |
| Failure labels | `FAILED_APPROACH`, `FAILED_GRASP`, `HORIZON_REACHED` |
| Effective object motion | NO |
| Experimental Pipeline | PASS |
| Task Transfer | FAIL |

这证明 cross-simulator evaluation pipeline 可以完整运行，但当前协议下 Pi0.5 没有完成任务。它不是 unseen-task、zero-shot new-task、open-world generalization 或 sim-to-real 结果。

## 5. 完整 Failure-analysis Story

```text
Step 6: 0/3
→ Action Parity Audit
→ State Mapping mismatch
→ State Mapping fix
→ Scripted Oracle
→ Tomato Safety false positive
→ Safety telemetry
→ floating-point comparison bug
→ minimal floating-point-safe fix
→ PINK finger configuration blocker
→ static audit
→ 9D arm+finger → 7D arm-only PINK
→ Tomato formal post-fix 3/3
→ Robot-side Oracle ROBUST PASS
→ One post-fix Pi0.5 diagnostic
→ NO_CLEAR_IMPROVEMENT
→ FREEZE_FRANKA_ISAAC_MAINLINE
```

### 5.1 Action semantics audit

没有确认 Action Adapter 中存在 sign、scaling 或 target-construction bug。观测到的短时平移差异属于 tracking magnitude mismatch；旋转差异与初始 EEF frame 不同有关。现有证据不允许把 Step 6 失败归为已确认的 action-semantics bug。

### 5.2 State Mapping

Position source 改为 `/World/Robot/panda_hand/tool_center` 后：

| 集合 | 修复前 mean / max | 修复后 mean / max |
| --- | ---: | ---: |
| Calibration | 37.870 / 70.814 mm | 7.874 / 8.207 mm |
| Hold-out | 62.852 / 79.705 mm | 7.800 / 7.898 mm |

Gripper state 改为：

```text
Isaac [finger1, finger2]
→ LIBERO-compatible [finger1, -finger2]
```

Position 和 gripper mapping 得到实证改善，但 orientation mapping 仍为 `UNRESOLVED`，因此整体 State Mapping 结论保持 `APPROXIMATE`。最大 image-state skew 约 `0.15 s`，作为已知限制保留。

### 5.3 Robot-side Scripted Oracle

Oracle 不调用 Pi0.5、不使用视觉识别或语言决策，只验证 Franka、PINK、Safety、gripper、PhysX 与场景物体链路。

原始固定六次正式结果：

- Alphabet soup：3/3；
- Tomato sauce：0/3；
- Tomato 三次均在 descent 阶段 `SAFETY_STOP`。

随后诊断明确定位到两个 robot-side blocker：

1. `panda_finger_joint2` 是 prismatic joint，其 target 仅比 upper limit 高约 `3.725e-9 m`，严格浮点比较将其误判为越界；
2. PINK 的 arm IK configuration 错误包含两个 finger joints，使夹爪浮点边界继续阻塞 arm IK。

最小修复：

- 使用 2 ULP 量级的浮点安全比较，不放宽物理安全阈值；
- PINK 从 9D arm+finger 改为 7D arm-only；
- gripper 保持独立控制。

Post-fix Tomato 三次 hard-reset 正式验证为 3/3。结合既有 Alphabet 3/3，当前 scripted robot-side manipulation pipeline 结论为 **ROBUST PASS**。

这里的 Alphabet 与 Tomato 结果不是 Pi0.5 成功率，也不证明 LIBERO transfer。它只说明当前 scripted robot-side grasp/lift pipeline 对两个目标物都已经得到成功验证。

### 5.4 Post-fix Pi0.5 Diagnostic

在 robot-side blockers 清除后，只做了一次明确标记为 `DIAGNOSTIC / NOT COUNTED` 的 episode：

| 指标 | 结果 |
| --- | --- |
| Initial state | Step 6 state 0 |
| Cycles | 100 |
| K | 1 |
| Termination | `HORIZON_REACHED` |
| Task success | NO |
| Alphabet movement | 0 |
| Tomato movement | 0 |
| Plausible grasp | NO |
| Safety violations | 0 |
| IK failures | 0 |
| Action clipping | 99/100 cycles |
| Close-command cycles | 64 |
| Closest close attempt to tomato | ~0.201665 m |
| Behavior change | `NO_CLEAR_IMPROVEMENT` |

可做出的结论是：已确认的 robot-side blockers 清除后，Pi0.5 cross-simulator behavior 仍未表现出明确改善。

不能做出的结论是：Pi0.5 本身已被证明无效。这里只运行了一个 diagnostic episode，而且 orientation、同步、domain gap、controller/embodiment 和 clipping 等限制仍然存在。

## 6. Known Limitations

1. **Orientation mapping：** `UNRESOLVED`，不添加未经证明的固定旋转补偿；
2. **Image-state synchronization：** 最大 skew 约 `0.15 s`；
3. **Simulator gap：** LIBERO/MuJoCo 与 Isaac/PhysX 的 renderer、视觉和动力学不同；
4. **Controller / embodiment：** LIBERO OSC_POSE 与 Isaac Franka/PINK 链路并不等价；
5. **Scene approximation：** 目标物 collision 与 camera calibration 仍存在近似；
6. **Sample size：** post-fix Pi0.5 只有一个 diagnostic episode；
7. **Action clipping：** post-fix diagnostic 为 99/100 cycles，未继续深挖；
8. **Completion-file handshake race：** 100 次 inference 和 100 cycles 均已完成，但 policy process 在顶层 completion file 生成前不到一秒检查，导致原始 exit code 1。该 orchestration race 不影响已完成 episode 的结果，但作为 tooling limitation 保留。

## 7. 项目贡献边界

### 7.1 本项目证明了什么

- 能执行 Pi0.5 continued fine-tuning；
- 能建立可复现的 checkpoint 与重点任务闭环评测；
- 能构建 Isaac / ROS 2 / Franka VLA robot runtime；
- 能进行真实的 `predict_action_chunk` closed-loop policy execution；
- 能建立 cross-simulator evaluation；
- 能系统化定位 action、state、Safety、IK/controller 各层问题；
- 能修复 state-interface、Safety 浮点边界和 controller architecture bug；
- 能用 scripted Oracle 隔离 policy-side 与 robot-side failure。

### 7.2 本项目没有证明什么

- 完整 LIBERO benchmark SOTA；
- unseen-task 或 open-world generalization；
- sim-to-real transfer；
- 真实机器人部署或 Pi0.5 real-world success；
- RL 或 LoRA improvement；
- world-model capability；
- 本项目重新实现或发明了 Pi0.5。

LeRobot 与上游项目提供 Pi0.5 implementation、dataset/policy/training framework 和 LIBERO integration。本项目贡献是环境与运行时集成、受控实验、评测协议、接口审计、故障定位、最小修复和证据边界管理。

## 8. 冻结决策

```text
status: FROZEN
reason: major robot-side blockers cleared,
        post-fix Pi0.5 diagnostic showed no clear improvement,
        further Franka deep-dive has low project ROI
additional_rollouts_allowed: false
```

Phase 1 的 checkpoint、训练日志、LIBERO evaluation、视频和图表，以及 Phase 2/3 的脚本、运行日志、Oracle 和诊断结果均必须原样保留。

## 9. Next Main Phase（只记录，不执行）

下一主阶段计划为 **SO-101 Real Robot**：

```text
R0 Hardware bring-up
R1 Leader-Follower teleoperation
R2 Camera + robot observation pipeline
R3 Demonstration dataset collection
R4 ACT baseline
R5 VLA baseline / Pi0.5 adaptation
R6 Real-robot closed-loop evaluation
R7 Failure analysis
R8 RL / HIL only after stable baseline
```

当前状态：`PLANNED_NOT_STARTED`。本轮未创建 SO-101 代码、未连接硬件、未启动任何下一阶段实验。

## 10. 结构化产物

- `results/phase3_final_summary/final_metrics.json`
- `results/phase3_final_summary/failure_analysis_timeline.json`
- `results/phase3_final_summary/confirmed_fixes.json`
- `results/phase3_final_summary/remaining_limitations.json`
- `results/phase3_final_summary/project_contribution_boundary.json`
- `results/phase3_final_summary/franka_isaac_freeze.json`
- `results/phase3_final_summary/summary.md`
