# Phase 3 / Step 7：跨仿真失败定位矩阵（当前状态）

## 阶段门禁

Step 7 要求先完成 RTX 5090 Isaac 全栈迁移验证（Stage A）。最初 attempt 因固定等待和 shell 初始化问题无效；修正后 attempt03 已通过。后续正式诊断尚未启动，仍不得把 Stage A 通过写成 task transfer 成功。

这不是对 Step 6 的重跑，也不是策略失败的新证据。

## Stage A 实际证据

- RTX 5090 Vulkan：`vulkaninfo --summary` 已保存，设备可识别。
- 基础 Isaac 首次冷启动约 110 秒后 ready；单相机、双相机读帧和 ROS2 bridge-only 分层测试均通过。此前日志末尾的 `isaacsim.sensors.experimental` 不是已确认卡点。
- PINK / Franka / OSQP：既有 `isaac_step4_synthetic.py` 在独立目录成功运行；6 个平移轴、3 个旋转轴和 gripper open/close/neutral 通过。`[0.1,0,0,0,0,0,0]` 的约定输入对应 +5 mm X 平移，合成验证通过。
- Stage A attempt03：双路 256x256 RGB、`/joint_states`、Observation Snapshot、一次真实 2k Pi0.5 `[1,50,7]` 输出和只执行 `action_chunk[0]` 均通过；机器人实际移动，无 OOM。

## 根因矩阵

| Candidate | Evidence For | Evidence Against | Status |
|---|---|---|---|
| RTX 5090 / Isaac migration | 无 | Vulkan、基础 Isaac、双相机、ROS2 bridge 和一次真实 VLA action 全部通过 | RULED OUT |
| Action mapping | 本次尚未做 LIBERO vs Isaac 的 matched action parity | 合成六轴/三旋转/gripper 映射通过；未发现具体 bug | UNLIKELY |
| State mapping | 尚未完成至少五姿态跨环境审计 | 无直接反证；固定 95.1035 mm offset 不能替代工作空间审计 | UNKNOWN |
| EEF calibration | 同上 | 无新的 runtime 测量 | UNKNOWN |
| Gripper / physics | 尚未运行 scripted grasp oracle | gripper joint open/close/neutral 合成命令通过，但这不等价于可抓取 | UNKNOWN |
| Camera external | 与 Step 6 的视觉分布差异尚未审计 | 已有 256x256 有效帧；未发现渲染故障 | POSSIBLE |
| Camera wrist | 与 Step 6 的视觉分布差异尚未审计 | 已有 256x256 有效帧；未发现渲染故障 | POSSIBLE |
| Rendering / background | 尚未与 LIBERO 作受控比较 | 已确认 RTX 渲染、单/双相机读帧正常 | POSSIBLE |
| Safety clipping | 未开始新的 Step 7 统计 | Step 6 原始 300-cycle 数据仍可离线分析，但未在本次阶段执行 | UNKNOWN |
| Policy distribution shift | Step 6 的行为失败仍存在 | 当前没有排除机器人侧/相机/状态链路，不能归因 policy | UNKNOWN |
| Other | 启动日志在扩展加载阶段停止，缺少明确 exception | 缺少足够证据 | UNKNOWN |

## 当前结论

**MULTI-FACTOR / NOT YET ISOLATED。**

RTX 5090 全栈迁移已排除为 Step 6 失败的原因；但动作一致性、工作空间状态/EEF 标定、抓取物理、视觉分布和策略输出差异仍未隔离。不能把 Step 6 的 0/3 归因于 Pi0.5、VLM、视觉、语言理解或 domain gap。

## 允许的下一步

下一步应按 Step 7 既定优先级进行 action semantics/dynamics parity；其目标是分别测量同一 normalized OSC_POSE action 在 LIBERO 与 Isaac+PINK 中的 EEF motion，不运行完整任务或训练。在此之前不重跑 Step 6，不做 LoRA/RL。
