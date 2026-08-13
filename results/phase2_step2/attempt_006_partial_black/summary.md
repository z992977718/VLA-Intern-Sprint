# Phase 2 / Step 2 运行总结

## 结论

**FAIL（被远程容器 Vulkan graphics capability 阻塞）。**

项目代码已建立 Isaac Sim 6.0.1 的两路 RtxCamera/CameraSensor、ROS2PublishImage writer 和 ROS 2 Observation Adapter；ROS 包已编译成功。真实运行时，Franka 与 `/joint_states` 仍可用，但 RTX renderer 无法创建 GPU Foundation，因此没有任何真实 RGB frame、Image topic、PNG 或完整 Observation Snapshot。

## 已完成

- Phase 1 Observation/State/Action/Language schema 源码审计；
- Isaac Franka 9 个 joint names 与实际消息顺序审计；
- name→position/velocity/effort 显式映射节点；
- external + wrist 两路 Camera 代码配置；
- 官方 6.0.1 `RtxCamera(tick_rate=10)` + `CameraSensor` + `ROS2PublishImage` 路径；
- ROS 2 package 编译，`observation_adapter_node` 可执行；
- 真实远程运行和 GPU/Vulkan 诊断；
- 无 OOM，实测 peak GPU memory 577 MiB。

## 失败证据

- `ros2_topics.txt` 只有 `/joint_states`、`/parameter_events`、`/rosout`；
- `ros2_topic_info.txt`：`Unknown topic '/phase2/external_camera/rgb'`；
- `run.log` / `isaac_runtime.log`：
  - `VkResult: ERROR_INCOMPATIBLE_DRIVER`
  - `GPU Foundation is not initialized!`
  - `IHydraTexture refResource had no GPU foundation`
- 容器有 CUDA device 和 `/dev/dri/renderD136`，但没有 `/dev/nvidia-modeset`；NVIDIA 官方文档要求容器创建时提供 `graphics` capability 才能运行 Vulkan。

## 未生成（不得伪造）

- `camera_sample.png` / 两路 Camera PNG
- `camera_metadata.json`（ROS frame metadata）
- `joint_state.json`（本轮 Adapter snapshot）
- `observation_snapshot.json`
- `timing.json`

## 安全边界

- `policy_loaded=false`
- `vla_action_sent=false`
- 未加载 2k checkpoint
- 未做 inference、抓取、MoveIt、IK 或 Step 3
- 没有修改 LeRobot/Isaac upstream

## 恢复条件

使用在容器创建时启用 NVIDIA Vulkan/OpenGL `graphics` capability、并能通过 Isaac Sim compatibility check 的运行环境，再原样重跑 `phase2/scripts/run_phase2_step2_observation.sh`。Camera/PNG/Snapshot 全部真实通过前，Step 2 保持 FAIL。
