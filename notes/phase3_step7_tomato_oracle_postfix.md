# Phase 3 / Step 7C.3：Tomato Safety 修复后 Oracle 验证

## 1. 本阶段只改变了什么

唯一变量是 Step 7C.2 已确认的 joint-limit 浮点比较逻辑。原始物理关节上下限、PINK、轨迹、控制器、PhysX 参数、物体参数、成功判据和 `MAX_JOINT_STEP_RAD=0.05` 均未改变。

旧比较：

```text
target < lower 或 target > upper -> SAFETY_STOP
```

新比较：

```text
target < lower - tolerance           -> JOINT_LOWER_LIMIT
lower - tolerance <= target < lower -> clamp 到 lower 后继续

target > upper + tolerance           -> JOINT_UPPER_LIMIT
upper < target <= upper + tolerance -> clamp 到 upper 后继续
```

NaN/Inf 仍直接拒绝，joint delta 大于 `0.05 rad` 仍直接拒绝。

## 2. dtype 与 tolerance

三次 Isaac runtime 均确认：

- PINK joint target：`float32`
- Isaac joint limit：`float32`
- 比较 dtype：`float32`
- tolerance：每个 joint 使用其 limit 附近 `2 ULP`
- finger limit `0.04` 附近 tolerance：`7.450580596923828e-09 rad`

这能覆盖已知的一个 float32 ULP 误差 `3.725290298461914e-09 rad`，但远小于具有物理意义的角度变化。容差只允许把 target 夹回原 physical limit，不扩展 joint range。

## 3. 单元测试

Isaac 启动前运行了 13 个纯数值测试，最终 `13/13 PASS`：

- upper：低于、等于、一个 ULP 超出、真实超限；
- lower：高于、等于、一个 ULP 超出、真实超限；
- NaN、`+Inf`、`-Inf`；
- joint delta 大于 `0.05 rad`；
- joint delta 等于 `0.05 rad`。

第一次测试暴露了测试实现中的两个问题：非有限值被重复分类，以及 float32 的 `0.05` 与 Python float64 的 `0.05` 比较不一致。该次结果保留为 `safety_unit_tests_attempt1.json`。修正测试辅助函数后，正式结果保存在 `safety_unit_tests.json`。这发生在 Isaac 启动前，没有产生额外 Oracle trial。

## 4. 三次正式 post-fix trial

固定只运行 Tomato PostFix 0、1、2；每次 hard reset，没有运行第 4 次，也没有重跑 Alphabet。

| Trial | pre-grasp | descent step 0 | 完整 descent | grasp pose | close | lift | 结果 |
|---|---:|---:|---:|---:|---:|---:|---|
| 00 | YES | PASS | NO | NO | NO | NO | `IK_FAILURE` |
| 01 | YES | PASS | NO | NO | NO | NO | `IK_FAILURE` |
| 02 | YES | PASS | NO | NO | NO | NO | `IK_FAILURE` |

三次 descent step 0 均出现同一个、被允许的夹回事件：

```text
joint: panda_finger_joint2
raw target: 0.04000000283122063
runtime upper: 0.03999999910593033
excess: 3.725290298461914e-09
tolerance: 7.450580596923828e-09
clamped target: 0.03999999910593033
reason: FLOAT_TOLERANCE_UPPER_CLAMP
Safety decision: PASS
```

因此，原来发生在 descent step 0 的 false-positive `JOINT_UPPER_LIMIT` 已消失。三次都继续运行到 descent 中段。

## 5. 新阻塞：PINK 内部 configuration-limit validation

三次 launch log 均报告：

```text
PINK solve_ik failed: Joint 8 violates configuration limits
0.0 <= 0.04000149667263031 <= 0.04
```

随后 `controller.forward(...)` 返回 `None`，Oracle 将结果分类为 `IK_FAILURE`。这不是项目 Safety helper 的再次拒绝：PINK 在返回新的 joint target 之前，先对传入的当前 configuration 做了自己的 joint-limit 检查。

每次最后保存的 descent 帧对应 step 72；下一保存点应为 step 84。因此现有证据只能把失败定位到 step 73～84，异常路径没有保存精确 step。不要伪造具体 step。

每个 trial 的 `descent_step0.json` 确认了一个 clamp。由于后续异常路径没有落盘完整 `joint_telemetry.json` 和 `safety.json`，只能写“至少确认 3 个 clamp”，不能声称全过程 clamp 总数精确等于 3。

## 6. Before / After

| 指标 | BEFORE FIX | AFTER FIX |
|---|---:|---:|
| Tomato success | 0/3 | 0/3 |
| descent step 0 通过 | 0/3 | 3/3 |
| 完整 descent | 0/3 | 0/3 |
| grasp stage reached | 0/3 | 0/3 |
| lift success | 0/3 | 0/3 |
| 原 false-positive Safety stop | 3 | 0 |
| 已确认真实 Safety rejection | 不适用 | 0 |

## 7. 正式结论

- Floating-point-safe Safety comparison：已由单元测试和三次 runtime step 0 验证。
- Tomato post-fix Oracle：`0/3`，`FAIL`。
- Robot-side Oracle：结合冻结的 Alphabet `3/3`，仍为 `PARTIAL`。
- Step 7C.3：`PARTIAL`，因为目标 Safety bug 已修复，但 Tomato 完整 grasp/lift 没有通过。
- 这不能证明 Safety bug 导致了 Step 6 Pi0.5 `0/3`；Step 6 没有记录相同 Safety stop，因此“有贡献”的判断为 `UNLIKELY`。
- 当前不应进行 post-State-Mapping Pi0.5 diagnostic rollout。应先单独审计 PINK 接收的 finger current-state 为什么在 descent 中漂到 `0.04000149667263031`，但本阶段没有实施第二个修复。

## 8. 未做事项

- 未修改 PINK 或真实 joint limit；
- 未调整夹爪命令、轨迹、physics、friction、mass、collision 或 success metric；
- 未运行第 4 次 trial；
- 未运行 Alphabet、Step 6、Pi0.5、训练、LoRA、RL 或 Full Fine-Tuning；
- 未覆盖原 `grasp_oracle/`、`tomato_safety_localization/`、`tomato_safety_diagnostic/` 结果。
