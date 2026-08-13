# RTX 5090 Isaac 启动分层诊断（2026-08-13）

## 目的

上一轮 Stage A 使用固定 150 秒 readiness 等待并失败。为避免把缓慢启动误判为功能故障，本次将基础 Isaac、相机和 ROS2 bridge 拆成四个独立进程；每个模式只在其最后一个真实 Python 调用返回后才标记 ready。没有加载 Pi0.5、没有控制 Franka、没有发布 ROS topic。

## 结果

| 模式 | 实际检查 | 结果 | 关键时间 |
| --- | --- | --- | --- |
| `base` | `SimulationApp` 构造后 10 次 `app.update()` | PASS | 首次冷启动约 109.98 秒返回 |
| `single_camera` | 一个 `RtxCamera + CameraSensor` 建立并读取 RGB | PASS | App ready 10.81 秒；读帧 17.88 秒 |
| `dual_camera` | 两个 `RtxCamera + CameraSensor` 建立并各读一帧 RGB | PASS | App ready 10.78 秒；读帧 13.76 秒 |
| `ros2_only` | `enable_extension("isaacsim.ros2.bridge")` 后 20 次 `app.update()` | PASS | App ready 10.88 秒；bridge 更新完成 11.52 秒 |

## 对四个问题的回答

1. **去掉 150 秒限制后能否 ready？能。**首次基础冷启动约 110 秒后 `SimulationApp` 返回，随后 10 次更新完成。该启动耗时本身低于 150 秒，但很接近门限；把固定墙钟门限用于全栈 readiness 容易误判。
2. **卡在哪个 extension / Python 调用？**原 Stage A 日志最后可见的是 `isaacsim.sensors.experimental` 启动行，但分层证据表明此时 Python 仍停在 `SimulationApp({...})` 构造调用，尚未进入项目的 camera 或 ROS2 Python 调用。不能称 `isaacsim.sensors.experimental` 为已确认卡点。
3. **单/双相机是否有问题？没有。**单相机和双相机都能建立并读取 RGB frame；双相机不是当前启动阻塞因素。出现的 DLSS 低分辨率 warning 不影响读帧成功。
4. **ROS2 是否导致卡住？没有。**不启 ROS2 的基础和相机模式均通过；启用 `isaacsim.ros2.bridge` 后，Isaac 内部 Humble `rclpy` 成功加载，bridge 及更新完成，没有卡住。

## 对 Stage A 的最小修正

- 原始失败目录 `results/migration_smoke_5090_isaac/` 原样保留。
- 新 attempt 使用 `results/migration_smoke_5090_isaac_attempt02/`，不会覆盖旧证据。
- 等待 `isaac_ready.json` 时不再设固定 150 秒墙钟上限；仅在 Isaac 进程自行退出时失败。
- Isaac 阶段保留 `phase2/scripts/isaac_env.sh` 的缓存和 EGL ICD 环境；`vla_env.sh` 仅在 Pi0.5 policy 子进程中加载，避免覆盖 Isaac 的缓存变量。

## 修正后 Stage A attempt03

修正后的独立目录为 `results/migration_smoke_5090_isaac_attempt03/`，并已通过。

- Vulkan、Isaac RaytracedLighting、ROS2 Humble bridge、两路 256x256 RGB、`/joint_states` 和 Observation Snapshot 均通过。
- Pi0.5 2k checkpoint 完成一次真实 `predict_action_chunk`，输出 `[1,50,7]` 且有限；只执行了 `action_chunk[0]`。
- Franka 实际移动；目标位置误差 1.099 mm，姿态误差 6.517 mrad；无 OOM、无 dtype/device mismatch、无 task rollout。
- Pi0.5 单次 action-chunk 调用为 741.562 ms，仅用于本次全栈迁移 smoke，不是正式性能 benchmark；Torch peak allocated/reserved 为约 8.87/9.20 GiB。
- 本次 ROS 近似配对的最大 image-to-joint timestamp skew 为 0.15 s。它没有阻塞 Stage A，但比旧 Step 2 的 0.05 s 大；后续任何 state/camera 对齐结论都必须保留这一测量限制。
