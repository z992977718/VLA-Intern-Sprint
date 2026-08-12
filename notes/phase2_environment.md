# Phase 2 环境决策

## 固定版本

```text
Isaac Sim = 6.0.1
ROS 2 = Humble
Ubuntu = 22.04.5 LTS
NVIDIA Driver = 595.71.05
GPU = NVIDIA RTX 6000D, 85,651 MiB
Installation method = NVIDIA 官方 Python package（远程外层容器不具备 Docker-in-Docker 条件）
```

## 服务器审计结论

- GPU compute capability：12.0；RTX 6000D 属于带 RT Core 的 RTX 系列。
- CPU：Intel Xeon Platinum 8470Q，208 logical CPUs。
- RAM：1.0 TiB，审计时约 898 GiB available。
- 系统 overlay：30 GB available；不得用于大型 Isaac Sim 数据。
- 持久化数据盘：`/root/autodl-tmp`，150 GB，总计使用 64 GB，剩余 87 GB。
- GLIBC：2.35，满足 Isaac Sim 6.0.1 Python package 的 GLIBC 2.35+ 要求。
- 当前未安装 ROS 2、Docker 或 NVIDIA Container Toolkit；没有 DISPLAY、VNC 或已配置 WebRTC 服务。
- 当前环境自身位于云平台容器中，因此不采用 Docker-in-Docker。

## 官方文档核验结果（2026-08-12）

- NVIDIA 当前稳定版为 Isaac Sim 6.0.1。
- 官方 x86_64 支持 Ubuntu 22.04/24.04，最低 32 GB RAM、50 GB SSD、16 GB VRAM。
- 官方明确不支持无 RT Core 的 A100/H100；本机为 RTX 6000D，不属于该限制。
- 官方当前 Linux 测试 driver 为 595.58.03；本机 595.71.05 满足要求，无需升级。
- Ubuntu 22.04 对应官方推荐 ROS 2 Humble。
- 远程 headless/cloud 场景官方优先推荐 Container；由于当前云实例已经是无 Docker 的受限容器，选择同样受官方支持的 Python package 安装。

## 路径与数据边界

```text
Isaac Sim Python environment = /root/autodl-tmp/isaac_sim/venv
Isaac/Omniverse cache = /root/autodl-tmp/isaac_cache
Isaac assets/data = /root/autodl-tmp/isaac_assets
ROS 2 workspace = /root/autodl-tmp/ros2_ws
Project Phase 2 files = /root/autodl-tmp/VLA-Intern-Sprint/phase2
```

只安装 Step 1 需要的 runtime，并使用在线 Franka asset；不下载完整 Isaac asset pack。不得移动或删除 Pi0.5 checkpoint、LIBERO assets、Hugging Face cache 或 Phase 1 results。

## 当前状态

```text
Hardware audit = PASS
Driver audit = PASS
OS audit = PASS
Minimum disk requirement = PASS（87 GB > 50 GB minimum，但低于 500 GB Good 建议）
Simulation execution = PASS
Remote visualization = NOT CONFIGURED
```

## Step 1 最终运行结果（2026-08-12）

- Isaac Sim `6.0.1` 已从独立 Python 3.12 环境成功 headless 启动。
- RTX/Warp 运行时识别 `NVIDIA RTX 6000D`、`sm_120` 和 83 GiB 设备内存。
- 官方 Franka Panda 6.0 在线 USD 加载到 `/panda`，physics 正常运行。
- ROS 2 Humble 与 Isaac 内置 Humble FastDDS 通过 `ROS_DOMAIN_ID=42` 通信。
- 实测峰值 GPU 显存为 577 MiB；没有 OOM。该数值只适用于无相机的 Step 1 简单场景。
- 远程 GUI/WebRTC 未配置；仿真执行成功与远程画面未配置分开记录。
