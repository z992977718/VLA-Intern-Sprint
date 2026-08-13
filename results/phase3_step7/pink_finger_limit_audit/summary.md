# Phase 3 / Step 7C.4：PINK Finger-Joint Configuration Limit 静态审计

## 结论

审计完成，判定 `PASS`。这里的 PASS 只表示静态调用链和直接根因已经定位，不表示 Tomato 抓取恢复成功。

直接根因已经确认：项目把 7 个 arm joint 和 2 个 finger joint 一起放入 PINK configuration。失败调用开始时，Isaac 当前 `panda_finger_joint2` 已经是 `0.04000149667263031 m`；该值被复制到 PINK `q[8]`。PINK 在构建 QP 前执行 `Configuration.check_limits()`，使用 `1e-6 m` tolerance 检查：

```text
q[8] > upper + 1e-6
0.04000149667263031 > 0.040001
```

因此 PINK 在 solve 前返回 `IK_FAILURE`，没有生成 velocity、q_next 或 target。

## Joint 8

`index 8 = panda_finger_joint2` 已由四条独立证据确认：

1. 项目 `JOINT_NAMES = ARM_JOINTS + FINGER_JOINTS`；
2. 场景初始化显式断言 Isaac `robot.dof_names` 顺序完全一致；
3. PINK loader 按 URDF 顺序收集所有 `nq > 0` joints；
4. Step 7C.2/7C.3 telemetry 的 index 8 一直映射为 `panda_finger_joint2`。

没有 joint-ordering bug。

## Finger 是否真正参与 PINK

- 存在于 configuration：`YES`
- 存在于 QP velocity：`YES`
- 被 panda_hand FrameTask 直接优化：`NO`，finger joints 位于 panda_hand 下游
- 被 PostureTask 优化：`YES`，PostureTask 使用完整 9D identity Jacobian
- 包含在 PINK output：`YES`
- 最终作为 finger actuator target 生效：`NO`，项目紧接着用独立 gripper command 覆盖 indices 7、8

因此当前结构不是完全解耦，而是“PINK 先计算 9D，再由项目覆盖两维 finger target”。

## T0～T7

| 阶段 | finger2 值 | 结论 |
|---|---:|---|
| T0 Isaac current q | `0.04000149667263031 m` | 已经超限 |
| T1 PINK input q | 同上，提升为 float64 | 按 name 映射到 q[8] |
| T2 solve 前 | 同上 | `check_limits()` 在此失败 |
| T3 velocity/target | 未产生 | QP 尚未构建 |
| T4 integration | 未执行 | 不是本次 integration overshoot |
| T5 merge | 未执行 | failing call 没有 target |
| T6 Safety input | 未到达 | 项目 Safety 未参与新失败 |
| T7 articulation command | 未发送 | failing call 没有新命令 |

## 数值边界

- finger joint 是 prismatic joint，单位为米，不是弧度。
- 当前 PINK excess：`1.49667263030923e-6 m`
- PINK 内部 tolerance：`1e-6 m`
- 超出 PINK tolerance 的部分：`4.96672630309226e-7 m`
- 项目 Step 7C.3 tolerance：`7.450580596923828e-9 m`
- 当前 excess 是项目 tolerance 的约 `200.88` 倍

因此不能通过扩大项目 Safety tolerance 处理。

## 更底层的 overshoot 来源

既有日志确认：最终独立 gripper target 是 float32 `0.04`，即 `0.03999999910593033 m`；但 Isaac measured current 有时会略高于这个 target。Step 7C.2 的 approach telemetry 已记录最大 `0.0400000177323818 m`。

精确到 `0.04000149667263031 m` 的中段 drive dynamics 没有被异常路径记录。因此，“位置驱动在硬上限附近的 tracking overshoot”是 `POSSIBLE`，但底层 PhysX 产生机制仍是 `UNRESOLVED`。

## 工程判断

这是一个局部项目架构问题：原意是 PINK 只控制 7D arm、gripper 独立控制；实际却把 fingers 也放入 PINK configuration、PostureTask、limit validation 和初始 output。

建议下一步为：`MINIMAL_FIX_AND_ONE_DIAGNOSTIC_TRIAL`，但本阶段不执行。

最小修复概念：加载 Franka PinkRobot 后，把 `controlled_joint_names` 限定为 `ARM_JOINTS`，并让 PinkIKController 使用 7D `robot_joint_space`。finger 继续只走现有独立 gripper command。不得修改 PINK upstream、joint limit、tolerance、Safety、physics 或 trajectory。

只有得到新的明确授权后，才允许运行一次 `DIAGNOSTIC / NOT COUNTED` Tomato trial。如果实现需要 fork PINK、构造复杂 reduced model 或进行 controller redesign，则停止 Franka 深挖并记录为 known limitation。

当前不应运行 Pi0.5 diagnostic rollout。
