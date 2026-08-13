# Phase 2 / Step 4 总结

## 结论

**PASS。** 实际安装源码确认了 Pi0.5/LIBERO 7 维动作语义与 robosuite `OSC_POSE` 缩放；Isaac Sim 6.0.1 官方 `PinkIKController` 完成 task-space target 到 Franka joint target 的转换。合成坐标、姿态、夹爪测试全部通过后，2k checkpoint 只执行了一次真实 inference，并且只执行 `action_chunk[0]`。剩余49个动作未执行，没有第二次 inference，没有形成 closed loop。

## 合成测试

- 平移：+x/+y/+z 各 5 mm，实际均同向；位置目标误差约 1.12–1.14 mm。
- 旋转：Rx/Ry/Rz 各 0.02 rad，实际均同轴同向；姿态目标误差约 1.13–4.70 mrad。
- 夹爪：OPEN 0.04 m、CLOSE 0 m、NEUTRAL 0.02 m 均通过。
- PINK controller latency：mean 1.825 ms，p95 1.977 ms。

## 一次 VLA 动作

- checkpoint：`002000/pretrained_model`
- inference：1 次，577.160 ms；无 OOM。
- raw first action：`[-0.026066, 0.029027, -0.421050, 0.011975, -0.008025, 0.328101, 1.019405]`
- bounded first action：`[-0.026066, 0.029027, -0.1, 0.011975, -0.008025, 0.05, 1.0]`
- 实际 EEF delta：`[-0.000085, 0.001460, -0.002225]` m。
- target position error：1.115 mm；target orientation error：7.030 mrad。
- command→movement：97.120 ms；PINK mean/p95：1.950/2.356 ms。
- robot moved：true。

注意：adapter 的绝对目标由 Observation 时的 EEF 生成；执行环境重新稳定后初态有约 4.1 mm 差异，但通过了 5 mm 一致性门。因此执行日志中的 commanded delta 是相对真实执行初态计算，不能直接把 raw action 当作相对 before pose 的米制位移。

## 边界

- 只证明单次 open-loop Action Adapter 与安全执行链；不是 VLA closed-loop rollout。
- 未抓取物体、未评测任务成功率、未进入 Step 5。
- 第二相机仍是虚拟 wrist-follow view，不是已标定实体 eye-in-hand。
