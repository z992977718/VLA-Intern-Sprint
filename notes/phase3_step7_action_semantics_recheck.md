# Phase 3 / Step 7A 动作语义复核

## 源码结论

远程实际环境为 `hf-libero 0.1.4`、`robosuite 1.4.0`。`osc_pose.json` 与源码确认：

- 输入为 7 维 `[dx, dy, dz, drx, dry, drz, gripper]`。
- 控制器先把平移输入裁剪到 `[-1, 1]`，再缩放到每轴 `[-0.05, 0.05]` 米。
- 旋转输入缩放到轴角 `[-0.5, 0.5]` 弧度。
- `control_delta=true`；目标位置是当前 EEF 位置加平移增量。
- 目标姿态是 `R_target = R_delta @ R_current`，属于左乘空间增量。
- Panda gripper 的源码语义为 `-1=open`、`+1=closed`；命令通过内部增量状态逐步更新夹爪。

## 实验协议

每个规范动作均独立启动/重置环境。LIBERO 端执行一次真实 `OffScreenRenderEnv.step(action)`，控制频率 20 Hz（0.05 秒）。Isaac 端执行现有 `Action Adapter -> Safety -> PINK -> Franka` 链路，并运行 3 个 Isaac 物理步（3/60 秒）。不调用 Pi0.5，不做任务 rollout，不训练。

## 解释边界

本实验比较的是单个 50 ms 控制周期后的实际跟踪结果，不是把两个模拟器的动力学强行视为相同。目标映射与实际 EEF 轨迹必须分开解释；`MISMATCH` 只能说明本协议下的方向/幅值跟踪不一致，不能直接归因于 VLM、Attention 或 Pi0.5 内部语义故障。
