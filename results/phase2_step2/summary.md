# Phase 2 / Step 2 运行总结

## 最终结论

**PASS（Attempt 007）**

RTX 6000D 服务器已经完成真实的 Isaac Sim 6.0.1 双 RGB + Franka joint state → ROS 2 Observation 数据链路。两路图像均通过程序像素统计和人工画面检查；Observation Adapter 正常退出，所有必需产物齐全。

## 最终配置

- GPU：NVIDIA RTX 6000D，85,651 MiB VRAM；driver 595.71.05。
- Isaac Sim：6.0.1，headless，`RaytracedLighting`。
- Vulkan：`VK_ICD_FILENAMES=/etc/vulkan/icd.d/my_nvidia_icd.json`，ICD 指向 `/lib/x86_64-linux-gnu/libEGL_nvidia.so.0`。
- Camera API：`RtxCamera(tick_rate=10)` + `CameraSensor` + `ROS2PublishImage`，未使用 deprecated `frameSkipCount`。
- 图像：两路均为 256×256、`rgb8`。
- 外部视角：`/World/ExternalCamera`，topic `/phase2/external_camera/rgb`。
- 第二视角：`/World/WristTrackingCamera`，topic `/phase2/wrist_camera/rgb`。
- 状态：`/joint_states`，包含 Franka 7 个 arm joints + 2 个 finger joints。

## 验收结果

```text
node_exit=0
missing=[]
invalid_frames=[]
peak_gpu_vram_mib=3265
max_image_to_joint_state_abs_delta_sec=0.05
OOM=NO
```

ROS 2 topic：

```text
/phase2/external_camera/rgb  sensor_msgs/msg/Image  publisher=1
/phase2/wrist_camera/rgb     sensor_msgs/msg/Image  publisher=1
/joint_states                sensor_msgs/msg/JointState publisher=1
```

画质统计：

| 视角 | 像素范围 | 像素均值 | 像素标准差 | 暗像素占比（RGB 最大值≤5） |
| --- | ---: | ---: | ---: | ---: |
| external | 0–255 | 90.81 | 61.13 | 0.182% |
| wrist tracking | 0–233 | 117.31 | 48.94 | 0.116% |

自动验收要求：文件齐全、节点成功退出、像素非恒定、标准差大于 1、暗像素占比低于 50%。最终两路均通过；人工打开 PNG 后也确认没有全黑或大面积黑屏。

## Vulkan 修复过程

首次运行失败，日志包含：

```text
VkResult: ERROR_INCOMPATIBLE_DRIVER
GPU Foundation is not initialized!
IHydraTexture refResource had no GPU foundation
```

系统原 ICD 指向 `libGLX_nvidia.so.0`。按照 AutoDL headless Vulkan 指引：

1. 安装 `vulkan-tools libvulkan1 libsm6 libegl1`；
2. 新增独立 `/etc/vulkan/icd.d/my_nvidia_icd.json`，指向 `libEGL_nvidia.so.0`；
3. 保留系统原 `/etc/vulkan/icd.d/nvidia_icd.json` 不变；
4. `vulkaninfo --summary` 实测退出码 0，识别 NVIDIA RTX 6000D 独立 GPU；
5. 将该 ICD 只注入项目 Isaac 启动环境后重跑。

## 失败尝试与证据保留

- Attempt 001：GLX ICD，Vulkan/GPU Foundation 初始化失败。
- Attempt 002–005：Vulkan 已恢复，但第二路相机为全黑帧；直接读取 Isaac `CameraSensor.get_data("rgb")` 证明黑帧发生在 ROS 发布之前。
- Attempt 006：第二视角不再全黑，但人工检查发现大面积黑屏；因此加严验收，未将其计为最终成功。
- Attempt 007：拉远跟随视角，像素与人工画面检查通过。

早期原始证据保存在各 `attempt_*` 子目录，未被当作最终结果，也未伪造图片。

## 重要边界

- 第二路当前是虚拟手腕跟随视角：相机位于 `/World`，每帧跟随 `panda_hand` 的世界位置并看向前下方工作区。
- 它不是已经标定、具有固定刚性外参的真实 eye-in-hand 相机；不能把当前结果包装为真实相机标定或实体机械臂传感器集成。
- `/joint_states` 的 9 个关节量还没有转换成 Phase 1 Pi0.5 需要的 8 维末端 pose + gripper state。
- 当前只使用 latest-message approximate pairing，未使用 `message_filters` 或硬实时同步。
- `policy_loaded=false`、`vla_action_sent=false`；没有加载 Pi0.5，没有 inference、控制、抓取、MoveIt 或 Step 3。
- 未修改 LeRobot 或 Isaac Sim 上游源码。

## 最终产物

- `camera_external.png`
- `camera_wrist.png`
- `camera_metadata.json`
- `direct_camera_stats.json`
- `joint_state.json`
- `observation_snapshot.json`
- `timing.json`
- `ros2_topics.txt`
- `ros2_topic_info.txt`
- `observation_adapter.log`
- `isaac_runtime.log`
- `gpu_timeseries.csv`
- `gpu_peak.txt`
- `run_status.json`

运行结束后，服务器无 Isaac/Adapter 残留进程，GPU 无计算任务。
