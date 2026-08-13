# Phase 3 / Step 7C.2：Tomato Safety Telemetry Diagnostic

## 诊断结果

- Trial：`DIAGNOSTIC / NOT COUNTED`
- Pre-grasp：完成
- Descent：已进入
- 触发位置：`descent step 0`
- PINK solve status：`TARGET_RETURNED`
- PINK target finite：`YES`
- Safety reason：`JOINT_UPPER_LIMIT`
- Step 7C.2：`PASS`（诊断目标完成，不代表抓取成功）

## 精确触发值

- Joint：`panda_finger_joint2`（index 8）
- Actual：`0.040000006556510925 rad`
- PINK target：`0.04000000283122063 rad`
- Runtime upper limit：`0.03999999910593033 rad`
- 超出上限：`3.725290298461914e-09 rad`
- Joint delta：`-3.725290298461914e-09 rad`

这是唯一 violation。没有 lower-limit violation，没有 non-finite target，也没有 joint-delta threshold violation。

## Joint delta

- 最大绝对 delta：`0.04410219192504883 rad`
- Joint：`panda_joint6`
- 阈值：`0.05 rad`（未修改）
- 超过阈值：`NO`
- 距离阈值余量：`0.005897808074951172 rad`

## 根因

已确认根因是：PINK 返回的 `panda_finger_joint2` 目标在 float 精度边界上比 runtime upper limit 高一个极小量，而当前 Safety 使用无容差的严格 `target > upper` 比较，因此拒绝整个 descent step 0。

这属于 joint-limit safety comparison 的数值边界问题，不是物理、接触、夹爪机械能力、Pi0.5、视觉或 timestamp 问题。

## 最小修复建议（未执行）

统一 joint target 与 runtime limit 的比较精度；只对明确位于浮点 epsilon 内的越界值夹回精确 limit，再执行命令。真正超过 tolerance 的目标仍必须触发 Safety，`0.05 rad` joint-delta 阈值保持不变。

若之后获得授权，应在独立 post-fix 目录运行三次相同协议的 tomato Oracle，并保留原 Step 7C `0/3` 结果不变。当前仍不应执行 Pi0.5 diagnostic rollout。

## 未改变内容

没有修改原 Oracle、正式 `3/6` 结果、PINK、轨迹、目标、orientation、physics、mass、friction、collision、joint limits 或 Safety threshold；没有运行 Pi0.5、训练或 Step 6。
