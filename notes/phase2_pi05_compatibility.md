# Phase 2 / Step 2：Pi0.5 Compatibility Report

## 对比结论

| 接口 | 结果 | 证据与原因 |
| --- | --- | --- |
| Images | `MISMATCH`（计划结构为 `PARTIAL`，运行未验收） | 项目代码配置了 external + wrist 两路 256×256 RGB，视角角色与 Phase 1 对应；但当前容器 Vulkan 初始化失败，没有 ROS image topic、真实 RGB 或 PNG，所以不能标为可用 |
| Robot state | `MISMATCH` | Phase 1 是末端位置 3 + axis-angle 3 + gripper qpos 2；Phase 2 当前是命名后的 7 arm + 2 finger joint state，语义和维度均不同 |
| Language | `PARTIAL` | Adapter 已定义固定字符串 `move the robot arm` 并计划写入结构化 snapshot；但因 Camera 阻塞，完整 snapshot 尚未成功保存，也尚未进入 Pi0.5 processor |
| Action space | `MISMATCH`（只审计） | Phase 1 是 LIBERO/robosuite OSC_POSE 相对 7 维；Phase 2 Step 1 的 `/joint_command` 是 7 个关节的绝对目标位置。两者都“7 维”不代表可直连，本阶段未发送 action |

## Camera 运行阻塞

2026-08-12 在 RTX 6000D 容器真实运行 Isaac Sim 6.0.1 后：

- USD Camera prim、Franka 与 ROS `/joint_states` 创建成功；
- `/phase2/external_camera/rgb` 和 `/phase2/wrist_camera/rgb` 没有出现；
- 日志明确为 `VkResult: ERROR_INCOMPATIBLE_DRIVER`、`GPU Foundation is not initialized!` 和 `IHydraTexture refResource had no GPU foundation`；
- `/dev/nvidia8`、CUDA 与 Warp 可用，但 `/dev/nvidia-modeset` 不存在；
- NVIDIA Container Toolkit 官方说明：默认未配置时只提供 `compute,utility`，OpenGL/Vulkan 必须在**创建容器时**提供 `graphics` capability。进程内设置环境变量不能补做宿主机的驱动挂载。

因此，这是“CUDA compute 可用，但 RTX/Vulkan graphics runtime 不完整”的容器能力问题，不是相机代码生成了黑图，更不是模型问题。

## 不可做的推断

- 不能因为 Camera prim 已创建就声称 Camera PASS。
- 不能生成占位 PNG 或用其他图像替代真实 ROS frame。
- 不能把 `/joint_states` 前 8 个值直接叫作 Pi0.5 robot state。
- 不能把 `/joint_command` 的 7 个 joint target 当作 LIBERO 7 维 action。

## 下一次重跑前置条件

需要能够通过 Isaac Sim 6.0.1 compatibility/Vulkan 检查、且容器具备 NVIDIA `graphics` capability 的实例或容器。重跑只执行 Step 2 脚本；仍不得加载 Pi0.5 或进入 Step 3。
