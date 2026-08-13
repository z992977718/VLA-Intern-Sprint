# Phase 3 / Step 7B.1 状态映射修复与静态复核

本目录仅复核既有十个静态姿态采样：未调用 Pi0.5，未训练，未执行任务 rollout，也未重跑 Step 6。

- 位置：改用 USD 原生 `/World/Robot/panda_hand/tool_center` 后，校准集误差为 7.874 mm（最大 8.207 mm），独立 hold-out 为 7.800 mm（最大 7.898 mm）。结论为 `APPROXIMATE`，不是 `MATCH`。
- 姿态：没有经过 frame semantics 证明的固定旋转，因此保持 `UNRESOLVED`。
- 夹爪：将 Isaac `[finger1, finger2]` 映射为 LIBERO-compatible `[finger1, -finger2]`；open/intermediate/closed 三种状态均与 LIBERO 符号约定一致，结论为 `MATCH`。
- 时间同步：最大 image-to-joint skew 仍为 0.15 s，本轮未修改。

旧状态映射可能影响 Step 6 的 0/3，但本轮不能证明它是唯一原因；Step 6 现在不应重跑。
