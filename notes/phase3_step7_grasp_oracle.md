# Phase 3 / Step 7C：Scripted Grasp Oracle

## 实验目的

本阶段验证的是 Isaac/Franka/PINK/夹爪/PhysX 这一侧的基本抓取能力，不是 Pi0.5 评测。Oracle 直接读取 live Isaac 场景中的目标物体 world pose 和活动碰撞盒几何，绕开 perception、语言决策和 Pi0.5。

## 协议

- 场景：复用 Step 6 initial state 0、Franka、桌面、alphabet soup、tomato sauce、basket、碰撞和物理设置。
- 控制：Isaac Sim `PinkIKController` + OSQP + Franka，真实关节运动。
- 轨迹：根据目标碰撞盒实时几何计算 top-down pre-grasp、grasp、lift；每次 hard reset。
- 正式试验：alphabet soup A0-A2，tomato sauce T0-T2，共 6 次，未追加重试。
- 抬升阈值：最大竖直位移至少 `0.060 m`，保持后最终竖直位移至少 `0.045 m`。
- 成功还要求：close target 持续下发、接触后的夹爪状态稳定、目标确实离开桌面并保持。夹爪实际宽度不要求归零，因为被物体阻挡时非零宽度是正常的。
- 姿态：Isaac top-down task-space rotation `diag(1,-1,-1)`，依据平行夹爪垂直下降选择；没有使用 LIBERO orientation mapping 或固定补偿旋转。

## 结果

| 目标 | 结果 | 关键证据 |
|---|---:|---|
| alphabet soup | `3/3` | 每次最大竖直位移 `146.264 mm`，最终保持 `145.774 mm`；approach/descent/lift 均通过 |
| tomato sauce | `0/3` | 三次均在 descent 阶段触发 `SAFETY_STOP`，没有进入有效 close/lift 证据 |
| 总体 | `3/6` | `PARTIAL` |

alphabet soup 三次结果在相同 fixed initial state 下完全一致，说明当前机器人侧脚本轨迹和 PhysX 抓取链路对该目标可工作。tomato sauce 的正式失败保留在各自 `exception.txt` 和 `result.json` 中，不能用“继续重试”改写。

## 失败分类

- alphabet soup：`SUCCESS` × 3。
- tomato sauce：`SAFETY_STOP` × 3，异常位置为 `execute_stage("descent", ...)`。
- 没有 Pi0.5、`predict_action_chunk`、训练、Step 6 重跑、物体 teleport、kinematic attach、人工干预或物理参数修改。

## 和 Step 6 的关系

Oracle 的结果说明：

- 对 alphabet soup，PINK、Franka、夹爪控制和 PhysX 至少具备真实抓取/抬升能力；这些因素作为 Step 6 `0/3` 的主要解释变得不太可能，但不能完全排除。
- tomato sauce 的 robot-side pipeline 尚未通过，且正式失败发生在安全检查阶段；因此不能把 Step 6 `0/3` 归因于 Pi0.5，也不能声称抓取物理已完全验证。
- 本实验不使用相机或 observation，因此 Step 7B 记录的 `0.15 s` image-to-joint skew 与本实验失败无关。

## 最终判定

`Step 7C = PARTIAL`。当前 robot-side grasp pipeline 不是 `ROBUST PASS`，因为两个目标没有都稳定通过且总体只有 `3/6`。

下一步若继续，应先定位 tomato sauce descent 的最小安全原因；在此之前不应启动 Pi0.5 diagnostic rollout、训练或调物理参数。

完整证据位于 `results/phase3_step7/grasp_oracle/`，视频位于 `assets/videos/phase3_step7_oracle_*.mp4`。
