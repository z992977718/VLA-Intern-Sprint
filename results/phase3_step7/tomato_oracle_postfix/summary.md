# Phase 3 / Step 7C.3：Tomato 浮点安全修复后验证

## 结论

- Step 7C.3：`PARTIAL`。
- Tomato BEFORE FIX：`0/3`（冻结结果）。
- Tomato AFTER FIX：`0/3`。
- descent step 0：`3/3` 通过；完整 descent：`0/3`。
- grasp stage：`0/3`；lift：`0/3`。
- 原来的 Safety false-positive：已消失。
- 新阻塞：三次均在 descent 中段由 PINK 内部配置上限检查返回 IK failure。

## 新失败证据

三次日志均报告：`Joint 8 violates configuration limits 0.0 <= 0.04000149667263031 <= 0.04`。每次最后保存的 descent 采样为 step 72；由于每 12 步保存一次，失败只能定位在 step 73～84，精确步数未被异常路径保存。

已确认的容差夹回事件为 3 次（每个 trial 的 descent step 0 各一次）。后续未保存完整 telemetry，因此不能把 3 写成全过程精确总数。

## 边界

没有运行第 4 次 trial，没有重跑 Alphabet、Step 6 或 Pi0.5，没有修改 PINK、物理、轨迹、成功判据或 0.05 rad joint-delta 阈值，也没有自动修复第二个问题。
