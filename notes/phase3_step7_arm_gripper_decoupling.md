# Phase 3 / Step 7C.5：Arm / Gripper IK 解耦

## 阶段结论

`Step 7C.5 = PASS`，但只表示项目侧手臂/夹爪架构缺陷已修复，并由一次 `DIAGNOSTIC / NOT COUNTED` Tomato 试验验证。历史正式统计保持不变：Alphabet `3/3`、Tomato `0/3`、Overall `3/6`。

## 修复前架构

- PINK configuration：`nq=9`、`nv=9`。
- PINK joints：7 个 `panda_joint*` + 2 个 `panda_finger_joint*`。
- 两个 finger 是 prismatic joints，单位为米。
- 独立 gripper 的实际 finger state 会进入 PINK live configuration；因此 finger2 的轻微实际越界能够在 QP solve 前阻断整个 arm IK。

## 最小修复

- 不修改 NVIDIA/PINK upstream。
- 根据实际 bundled Franka URDF，在项目结果目录生成 arm-only URDF；只移除两根 finger joint 及其下游 fingertip 子树。
- PINK `FrameTask` 仍控制实际 `panda_hand`。
- PINK `PostureTask`、configuration、velocity、integration 和 target extraction 均变为真正的 7D arm-only 空间。
- Isaac articulation 中，7D arm target 与 2D gripper target 通过两个互不重叠的 selected-index command 独立发送。
- finite、joint limit、`0.05 rad` arm joint-delta 和 2-ULP floating-safe Safety 逻辑保持不变；finger target 继续走独立 Safety 检查。
- 未修改 physics、friction、mass、collision、drive、trajectory、PINK cost、OSQP、grasp target 或 success metric。

曾尝试使用 Pinocchio `buildReducedModel()`，但 bundled URDF 中的重复 frame 名会使该 API 拒绝构造。最终采用项目侧生成 arm-only URDF；原 bundled URDF 未被修改。

## A–H 门禁

- A：PINK configuration dimension = 7，PASS。
- B：controlled joints 恰好等于 7 个 `ARM_JOINTS`，PASS。
- C/D：finger1、finger2 均不在 PINK configuration，PASS。
- E：PINK index 0~6 精确映射 Isaac `panda_joint1~7`，PASS。
- F：gripper 可独立生成 2D finger target，PASS。
- G：最终 articulation arm/finger mapping 无错位、无重叠，PASS。
- H：Step 7C.3 Safety regression `13/13 PASS`。

全部测试在 Isaac 启动前完成；单元测试阶段不需要 GPU。

## 唯一 Tomato Diagnostic

- 类型：`DIAGNOSTIC / NOT COUNTED`。
- 运行次数：1；没有第二次 trial。
- initial state：0。
- PINK runtime configuration：`nq=7`、`nv=7`。
- pre-grasp：完成。
- descent：进入并完成，最大 control step = 199。
- 原失败区间 step 73~74：通过。
- `Joint 8 violates configuration limits`：未再次出现。
- grasp stage：到达。
- gripper close：已执行。
- 专用 contact sensor：未使用，因此不声称直接测得 contact。
- 物体运动：已观察；最大竖直位移 `0.1465308666 m`。
- lift：进入并成功；最终竖直位移 `0.1458925009 m`，阈值 `0.060 m`。
- exception：无。
- exit code：0。
- runtime：`22.8412 s`。
- Pi0.5 / `predict_action_chunk`：均未调用。
- OOM：无。
- RTX 5090 结束状态：`0 MiB / 0%`。

## 证据边界

这一次成功只能称为 `DIAGNOSTIC SUCCESS`。它确认已定位的本地 arm/gripper 架构问题被修复，不会把历史 Tomato `0/3` 改成 `1/3`，也不能证明 Tomato formal Oracle 已经稳健。它不是 Pi0.5 成功率、LIBERO transfer、跨域泛化或真实机器人部署结果。

如果获得新授权，下一步可以运行一组新的、独立命名的固定协议 Tomato `3/3` 验证；不得覆盖或回写历史正式结果。当前 Pi0.5 diagnostic rollout 仍为 `NO`。

## 证据文件

完整结果位于 `results/phase3_step7/arm_gripper_decoupling/`。核心文件包括架构前后、joint mapping、A–H 测试、逐 step descent/PINK/gripper/Safety telemetry、单次 trial 结果、冻结哈希、代码 diff 与中文摘要。
