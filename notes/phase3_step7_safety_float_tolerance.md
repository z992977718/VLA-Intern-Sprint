# Phase 3 / Step 7C.3：Joint-limit 浮点容差设计

## 已确认问题

Step 7C.2 中 `panda_finger_joint2` 的 PINK target 为 `0.04000000283122063 m`，Isaac runtime upper limit 为 `0.03999999910593033 m`，两者只差 `3.725290298461914e-09 m`。Step 7C.4 源码审计确认该 joint 为 prismatic joint；此前写成 `rad` 是单位标签错误，不改变数值结论。

该差值等于 `0.04` 附近一个 float32 ULP（相邻可表示浮点数的间距）。旧代码使用无容差的 `target > upper`，因而把一个表示精度边界判为真实越界。

## 为什么不使用固定大容差

不采用统一的 `1e-3` 或 `1e-2` native joint unit。对 revolute joint 它们是弧度，对 prismatic finger joint 则是米；两种情况都已经可能具有物理意义，等同于放宽 joint range。

也不预设统一的 `1e-6`。不同 joint limit 的数值量级不同，浮点间距也不同，固定值缺乏 dtype 和量级依据。

## 选择：每个 limit 两个 ULP

实现会在运行时读取：

- PINK raw joint target array dtype；
- Isaac joint lower/upper array dtype。

比较采用两者中精度较低的浮点 dtype，并为每个 joint 计算：

```text
tolerance = 2 * max(abs(spacing(lower)), abs(spacing(upper)))
```

选择两个 ULP 的理由：

1. 已知错误是一个 float32 ULP，两个 ULP 足以覆盖同类 source/API round-trip；
2. tolerance 随真实 dtype 和 limit 量级变化，不是人为放宽固定角度；
3. 对 prismatic finger upper limit `0.04 m`，预计 tolerance 仅约 `7.45e-09 m`；
4. target 最终会夹回原始 physical limit，而不是把 limit 向外扩展；
5. 超过 `upper+tolerance` 或低于 `lower-tolerance` 仍然拒绝；
6. NaN/Inf 和现有 `0.05` joint-delta 检查完全不变；代码中的 `_rad` 命名只适用于 revolute joints，finger delta 的真实单位是米。

## 运行时 dtype 验收

本文件在 Isaac 启动前记录设计依据。实际 post-fix trial 会另外保存 `float_tolerance_runtime.json`，以真实 runtime array 为准确认：

- `target_source_dtype`
- `joint_limit_source_dtype`
- `comparison_dtype`
- 每个 joint 的 tolerance

若实际 dtype 与预期不同，函数会自动按真实较低精度 dtype 计算 ULP，不静默套用 float32 常量。

## Safety 语义

```text
target > upper + tolerance      -> REJECT: JOINT_UPPER_LIMIT
upper < target <= upper + tol   -> clamp(target, upper) + PASS

target < lower - tolerance      -> REJECT: JOINT_LOWER_LIMIT
lower - tol <= target < lower   -> clamp(target, lower) + PASS
```

## Runtime 验收补充（2026-08-13）

三次 post-fix trial 均实际确认 target、joint limit 和 comparison dtype 为 `float32`。finger joint 的 `2 ULP` tolerance 为 `7.450580596923828e-09 m`。三次 descent step 0 均把一个 ULP 的超出夹回原 upper limit 并通过 Safety；没有放宽 physical limit。

随后三次均在 descent 中段出现新的 PINK 内部 configuration-limit `IK_FAILURE`。这是独立的后续问题，不属于本 tolerance 修复，也未在 Step 7C.3 中继续修改。

这项修复只解决数值比较。它不修改 USD/runtime joint limit、不关闭 Safety、不改变 PINK、轨迹、物理或 `MAX_JOINT_STEP_RAD=0.05`。
