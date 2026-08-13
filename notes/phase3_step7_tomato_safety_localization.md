# Phase 3 / Step 7C.1：Tomato Sauce 下降阶段安全停止定位

## 本轮范围

本轮只读取已有 Step 7C 文件和源码进行静态分析，没有重新运行 Isaac Sim，没有增加 trial，没有调用 Pi0.5 或 `predict_action_chunk`，也没有修改安全阈值、控制器、物理参数或正式六次结果。

## 已确认事实

1. `tomato_00/01/02` 都在 `execute_stage("descent", ...)` 中抛出 `RuntimeError("SAFETY_STOP")`。
2. 每个 trial 都保存了 23 张帧：start 1、open 1、approach 21、descent 0。
3. `execute_stage` 在 step 0 通过安全检查后必定执行 physics step，并因 `index % 12 == 0` 立即保存 descent 帧。
4. 因此三次都可定位为 **descent step 0 的安全门拒绝**。
5. 三次异常文件哈希相同，说明异常栈一致；仍不能证明底层安全条件完全相同。

## 安全分支真实语义

当前源码把四类条件合并在同一个 `if`：

- `joint_target` 存在 NaN/Inf；
- `max(abs(joint_target-current)) > 0.05 rad`；
- `joint_target < lower_limit`；
- `joint_target > upper_limit`。

失败时只在内存中的 `safety["events"]` 添加 stage、step 和聚合后的 `joint_step_rad`，随后立刻抛异常。异常处理没有写出 `safety.json`、`trajectory.json`、`eef.json` 或 `controller.json`，所以底层触发条件和数值全部丢失。

## PINK 判定

不能把本次简单写成 `IK_FAILURE`。若 PINK reset 失败或 forward 没有返回位置，代码会抛出带 `IK_FAILURE` 的另一类异常。当前异常发生在 forward 返回目标之后的安全门。

准确表述是：**PINK 返回了一个 joint target，但该 target 被聚合安全检查拒绝；它究竟是非有限、跳变过大还是越过关节限位，现有日志无法确定。**

## Workspace 判定

Step 7C Oracle 没有显式 Cartesian workspace min/max 检查。Step 6 的 workspace 常量没有在此处执行，因此 workspace 不是本次 `SAFETY_STOP` 的直接代码分支。

这不等于证明目标在机械臂完整可达空间内；它只说明本次异常不能被标记为“workspace gate 触发”。

## 几何对照

- Alphabet 成功目标（真实已保存）：pre-grasp/grasp/lift z 为 `0.609104/0.524104/0.669104 m`。
- Tomato 的失败 trial 没有保存 live target。
- 既有 dynamic scene export 中 tomato 根位置、近似 collider center/half-extents 均为有限值；标量 z 重建约为 `0.608242/0.523242/0.668242 m`。
- Tomato 的最终 approach 截图显示夹爪位于目标物上方。

所以目前没有“目标写进物体内部”或“高度明显异常”的证据，但 collider 本身是 `APPROXIMATE ASSET`，且失败 trial 的精确 live Gf target 未保存，不能宣称几何已完全排除。

## Joint delta 与 joint limit

`JOINT_DELTA_LIMIT` 是下一次遥测最值得优先查看的候选，因为异常恰好发生在 approach→descent 的 stage reset 后第 0 步。但这只是诊断优先级，不是已证明根因。

成功 alphabet 的已有轨迹中，60 个降采样点在 `world.step` 后的 target-actual 最大差为 `0.041172 rad`，低于 `0.05 rad`；这个量不是安全门检查的命令前 `step_size`，只能作为参考。

Tomato 没有保存 joint target、actual 和 limits，因此 joint delta 与上下限都保持 `UNRESOLVED_FROM_EXISTING_LOGS`。

## 最小建议（未执行）

只增加诊断记录，不改变行为：

1. 把四个安全条件拆成独立布尔字段；
2. 抛异常前原子写出 trigger JSON；
3. 保存 joint target/actual、逐关节 delta、argmax、lower/upper limit 和 margin；
4. 同时保存 EEF target/actual 与 live object geometry；
5. 如获授权，只运行一次 `DIAGNOSTIC / NOT COUNTED` tomato trial。

当前不应放宽 `MAX_JOINT_STEP_RAD`，不应修改关节限位、PINK、物理、摩擦、质量或碰撞体，也不应进行 Pi0.5 diagnostic rollout。

## 最终结论

- 三次相同到什么程度：相同 stage、相同 step 0、相同高层异常；底层 leaf 未证实相同。
- Root cause：`UNRESOLVED_FROM_EXISTING_LOGS`。
- 最具体定位：`DESCENT_STEP_0_SAFETY_GATE_REJECTION`。
- 是否已修复：否。
- 是否需要重跑才能得到精确 leaf：是，但必须等待用户授权，且只需一次非计数诊断。
- 现在是否执行 Pi0.5 diagnostic rollout：`NO`。
