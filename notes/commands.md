# 命令记录

## 2026-08-13：Phase 3 / Step 7 Stage A（仅远程执行，FAIL-FAST）

Stage A 使用独立目录，禁止覆盖 Phase 1、Step 6 的任何结果：

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint
bash phase3/scripts/run_stage_a_5090_full_stack.sh
```

最初 attempt 因固定等待与 ROS setup shell 严格模式退出而无效，已保留原始日志。修正后 attempt03：Vulkan、Isaac、ROS2、双相机、PINK 和一次真实 VLA action 均通过。`action_chunk=[1,50,7]`、finite，仅执行 index 0；未训练、未执行 task rollout。

产物：`results/migration_smoke_5090_isaac/`；启动日志：`results/stage_a_5090_launcher.log`。

## 2026-08-13：RTX 5090 克隆迁移审计（仅远程执行）

新服务器入口：

```bash
ssh -p 22705 root@connect.westd.seetacloud.com
```

加载项目环境并确认 Python 入口：

```bash
source /root/autodl-tmp/vla_env.sh
echo "$VLA_PYTHON"
```

最小迁移 smoke test（不会训练，不执行 `env.step()`，不覆盖旧结果）：

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint
"$VLA_PYTHON" scripts/check_5090_migration.py \
  --checkpoint results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model \
  --output-dir results/migration_smoke_5090_20260813
```

本次实际结果保存在 `results/migration_smoke_5090_20260813/`：2k checkpoint 加载成功，LIBERO task 0 reset 成功，一次真实 `predict_action_chunk` 输出 `[1,50,7]` 且全为 finite；OOM=NO，动作未执行。单次 smoke latency 为 556.762 ms，不能替代正式多次 profiling。

## Phase 2 / Step 2：Camera + Robot State → Observation（仅远程；PASS）

已实现入口：

```bash
# 构建项目自有 ROS 2 package
source /opt/ros/humble/setup.bash
cd /root/autodl-tmp/ros2_ws
colcon build --packages-select vla_manipulator_runtime --symlink-install
source install/setup.bash
ros2 pkg executables vla_manipulator_runtime

# 配置 AutoDL headless EGL Vulkan ICD（幂等，会新增独立 ICD，不覆盖系统原 ICD）
bash /root/autodl-tmp/VLA-Intern-Sprint/phase2/scripts/configure_headless_vulkan_icd.sh

# 构建项目自有 ROS 2 package
source /opt/ros/humble/setup.bash
cd /root/autodl-tmp/ros2_ws
colcon build --packages-select vla_manipulator_runtime --symlink-install

# 运行双 RGB + joint state → Observation 验收
bash /root/autodl-tmp/VLA-Intern-Sprint/phase2/scripts/run_phase2_step2_observation.sh
```

安装 Vulkan 诊断工具（本服务器已执行）：

```bash
apt-get update
apt-get install -y --no-install-recommends vulkan-tools libvulkan1 libsm6 libegl1
```

ICD 验收必须识别到 NVIDIA 独立 GPU：

```bash
VK_ICD_FILENAMES=/etc/vulkan/icd.d/my_nvidia_icd.json vulkaninfo --summary
```

本机实测：`PHYSICAL_DEVICE_TYPE_DISCRETE_GPU`、`NVIDIA RTX 6000D`、driver `595.71.05`、退出码 0。

验收 topic：

```bash
export ROS_DOMAIN_ID=42
source /opt/ros/humble/setup.bash
source /root/autodl-tmp/ros2_ws/install/setup.bash

ros2 topic list
ros2 topic info --verbose /phase2/external_camera/rgb
ros2 topic info --verbose /phase2/wrist_camera/rgb
ros2 topic info --verbose /joint_states
ros2 run vla_manipulator_runtime observation_adapter_node
```

2026-08-12 最终 Attempt 007 实测：

```text
/phase2/external_camera/rgb  sensor_msgs/msg/Image  publisher=1
/phase2/wrist_camera/rgb     sensor_msgs/msg/Image  publisher=1
/joint_states                sensor_msgs/msg/JointState publisher=1
node_exit=0
missing=[]
invalid_frames=[]
peak_gpu_vram_mib=3265
max_image_to_joint_state_abs_delta_sec=0.05
```

两路均为 256×256 `rgb8` 真帧。外部相机暗像素占比为 0.182%，第二路手腕跟随视角为 0.116%。第二路是随 `panda_hand` 世界位置移动的虚拟 tracking view，不是已经标定的刚性 eye-in-hand 实体相机。

首次失败证据保存在 `results/phase2_step2/attempt_001_glx_icd_failure/`：

```text
/joint_states
/parameter_events
/rosout
Unknown topic '/phase2/external_camera/rgb'
VkResult: ERROR_INCOMPATIBLE_DRIVER
GPU Foundation is not initialized!
```

诊断命令：

```bash
nvidia-smi --query-gpu=name,pci.bus_id,display_active,display_mode --format=csv,noheader
ls -l /dev/nvidia* /dev/dri/*
cat /etc/vulkan/icd.d/nvidia_icd.json
grep -E 'ERROR_INCOMPATIBLE_DRIVER|GPU Foundation|IHydraTexture' \
  /root/autodl-tmp/VLA-Intern-Sprint/results/phase2_step2/isaac_runtime.log
```

本服务器通过 AutoDL 官方 headless ICD 方案恢复：新增 `/etc/vulkan/icd.d/my_nvidia_icd.json`，其 `library_path` 指向 `/lib/x86_64-linux-gnu/libEGL_nvidia.so.0`；原 `/etc/vulkan/icd.d/nvidia_icd.json` 保持不变。

## Phase 2 / Step 1：Isaac Sim + ROS 2 + Franka 最小闭环（仅远程执行）

固定环境：Ubuntu 22.04.5、Driver 595.71.05、RTX 6000D、Isaac Sim 6.0.1、ROS 2 Humble。

```bash
# ROS 2 Humble（Ubuntu 22.04 官方二进制包）
apt-get update
apt-get install -y --no-install-recommends \
  ros-humble-ros-base python3-colcon-common-extensions python3-rosdep \
  python3-pip build-essential

# Isaac 专用 Python 3.12 环境位于数据盘
/root/autodl-tmp/miniforge3/bin/conda create -y \
  -p /root/autodl-tmp/isaac_sim/venv python=3.12 pip

# 用户已明确同意 NVIDIA EULA
export OMNI_KIT_ACCEPT_EULA=YES
bash /root/autodl-tmp/VLA-Intern-Sprint/phase2/scripts/install_isaac_step1.sh

# 构建项目自己的最小 ROS 2 节点
cd /root/autodl-tmp/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
ros2 pkg executables vla_manipulator_runtime

# 已验证的完整闭环与显存采样入口
bash /root/autodl-tmp/VLA-Intern-Sprint/phase2/scripts/run_phase2_step1_smoke.sh
```

若分开启动，Isaac 端必须先加载环境文件，其中包含内部 Humble 库路径和 `ROS_DOMAIN_ID=42`：

```bash
source /root/autodl-tmp/VLA-Intern-Sprint/phase2/scripts/isaac_env.sh
$ISAAC_ENV/bin/python \
  $ISAAC_PROJECT/phase2/scripts/isaac_franka_ros2_bridge.py
```

另一个终端：

```bash
export ROS_DOMAIN_ID=42
source /opt/ros/humble/setup.bash
source /root/autodl-tmp/ros2_ws/install/setup.bash
ros2 topic list -t
ros2 topic echo /joint_states --once
ros2 run vla_manipulator_runtime franka_joint_command_test
```

最终一键复现实测结果：节点退出码 0，`robot_moved=true`，`target_reached=true`，最大关节误差 0.0560 rad，peak GPU VRAM 577 MiB，无 OOM。

> 为确保命令可以直接复制执行，代码块、参数名、路径、软件包名和真实终端输出保留原文；其余说明均使用中文。

## LeRobot + SmolVLA + LIBERO 远程环境

> 执行边界：本节全部内容仅用于远程 Linux GPU 服务器。
> 不得在本地 Windows 或 WSL 执行。
>
> 状态：已通过源码确认，并于 2026-08-10 在 AutoDL RTX 4090 服务器完成运行验证。当时尚未开始训练。

### 证据与固定源码版本

- 仓库：`https://github.com/huggingface/lerobot.git`
- 已检查 commit：`22bd7a2f489b367d8df42de803b1e8c4ca63a3f9`
- LeRobot 版本：`0.6.2`
- 证据文件：
  - `pyproject.toml`
  - `docs/source/installation.mdx`
  - `docs/source/smolvla.mdx`
  - `docs/source/libero.mdx`
  - `docker/Dockerfile.benchmark.libero`
  - `src/lerobot/envs/libero.py`

### 已确认要求

- Python：`>=3.12`；服务器使用 Python 3.12。
- PyTorch 核心版本范围：`torch>=2.7,<2.12.0` 和
  `torchvision>=0.22.0,<0.27.0`.
- `training`：dataset 依赖、Accelerate 和 Weights & Biases。
- `smolvla`：Transformers、num2words 和 Accelerate。
- `libero`：dataset、Transformers、SciPy，以及 Linux 上的
  `hf-libero>=0.1.4,<0.2.0` on Linux.
- 在该依赖定义中，LIBERO 仅支持 Linux。
- LIBERO 使用 MuJoCo。在无界面服务器初始化、Rollout 或 Evaluation 前设置 `MUJOCO_GL=egl`。
- 计划中的 SmolVLA GPU 工作负载需要 CUDA，但这与安装 LIBERO Python package 是两回事。
- 推荐的 `lerobot/libero` 数据集使用 TorchCodec/PyAV 解码视频；conda 安装路径应提供 ffmpeg。

## 仅远程执行的安装流程

### 1. Preflight：修改服务器前先检查

```bash
uname -a
uname -m
cat /etc/os-release
nvidia-smi
python3 --version
df -h
```

只有确认主机为 Linux、NVIDIA GPU/driver 可见，并且磁盘足够容纳 CUDA wheels、模型权重、数据集和日志后才能继续。

当前 LeRobot 文档使用 CUDA 12.8 wheels，并要求 NVIDIA driver 至少为 `570.86`。若远程 driver 更旧，应在此停止，检查服务器细节后选择兼容的 PyTorch CUDA build；不得静默替换 CUDA build。

### 2. 创建隔离的 Python 3.12 环境

当前官方安装指南建议通过 Miniforge 使用 conda：

```bash
conda create -y -n vla-intern python=3.12
conda activate vla-intern
conda install -y ffmpeg=7.1.1 -c conda-forge
python -m pip install --upgrade pip
```

### 3. Checkout 已检查的准确 LeRobot revision

```bash
git clone https://github.com/huggingface/lerobot.git
cd lerobot
git checkout --detach 22bd7a2f489b367d8df42de803b1e8c4ca63a3f9
git rev-parse HEAD
```

预期 commit：

```text
22bd7a2f489b367d8df42de803b1e8c4ca63a3f9
```

### 4. 安装 CUDA PyTorch 和最小 LeRobot extras

适用于 driver 满足 CUDA 12.8 要求的服务器：

```bash
python -m pip install \
  --index-url https://download.pytorch.org/whl/cu128 \
  "torch>=2.7,<2.12.0" \
  "torchvision>=0.22.0,<0.27.0"

python -m pip install -e ".[training,smolvla,libero]"
```

最小 LeRobot extras 命令为：

```bash
python -m pip install -e ".[training,smolvla,libero]"
```

不要安装 `.[all]`，它会加入无关 policy、模拟器、硬件和开发依赖。

若因缺少系统开发库导致源码构建失败，官方 troubleshooting 提供以下可选修复步骤。不要预先执行：

```bash
sudo apt-get install cmake build-essential python3-dev pkg-config \
  libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev \
  libswscale-dev libswresample-dev libavfilter-dev
```

### 5. 非交互准备 LIBERO assets

将 assets 保存在 AutoDL 持久化数据盘。`hf-libero==0.1.4` 当前通过固定路径 `~/.cache/libero/assets` 查找下载资源；它的 `get_assets_path()` 不使用 `~/.libero/config.yaml` 中的 `assets` 配置。先下载到数据盘，再在固定 cache 路径创建小型 symlink；这不会修改 LeRobot 源码。

```bash
export LIBERO_ASSET_DIR=/root/autodl-tmp/cache/libero-assets
mkdir -p "$LIBERO_ASSET_DIR"

python -c "from huggingface_hub import snapshot_download; print(snapshot_download(repo_id='lerobot/libero-assets', repo_type='dataset', local_dir='/root/autodl-tmp/cache/libero-assets', max_workers=1))"

mkdir -p "$HOME/.cache/libero"
test ! -e "$HOME/.cache/libero/assets" || test -L "$HOME/.cache/libero/assets"
ln -sfn "$LIBERO_ASSET_DIR" "$HOME/.cache/libero/assets"

test -f "$HOME/.cache/libero/assets/scenes/libero_living_room_tabletop_base_style.xml"
ls -ld "$HOME/.cache/libero/assets"
```

在 AutoDL 上，如果无法直连 Hugging Face，可在 `snapshot_download` 前执行 `source /etc/network_turbo`。不要为 pip mirror 开启该加速器。

## 仅远程执行的验证流程

### 6. 验证依赖一致性、import、版本和 CUDA

```bash
python -m pip check

python -c "import sys, torch, lerobot, libero; print('python:', sys.version); print('torch:', torch.__version__); print('lerobot:', lerobot.__version__); print('libero:', libero.__file__); print('cuda_available:', torch.cuda.is_available()); print('torch_cuda:', torch.version.cuda); print('gpu:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else None); assert torch.cuda.is_available(), 'CUDA is not available'"
```

验收信号：

- `pip check` 不报告 broken requirements；
- `torch`、`lerobot`、`libero` import 成功；
- `cuda_available: True`.
- 输出 `torch_cuda` 和真实 GPU 名称。

### 7. 初始化并 Reset 一个真实 LIBERO 环境

当前 LeRobot API 在第一次 `reset()` 时才延迟创建 `OffScreenRenderEnv`，因此仅 import 成功不足以完成验证。

```bash
export MUJOCO_GL=egl

python - <<'PY'
import torch
import lerobot
import libero
from lerobot.envs.factory import make_env, make_env_config

cfg = make_env_config(
    "libero",
    task="libero_10",
    task_ids=[0],
    observation_height=64,
    observation_width=64,
)
envs = make_env(cfg, n_envs=1)
env = envs["libero_10"][0]
obs, info = env.reset()
print("LIBERO_RESET_OK")
print("observation_keys:", sorted(obs.keys()))
print("action_space:", env.action_space)
print("cuda_available:", torch.cuda.is_available())
env.close()
print("LIBERO_CLOSE_OK")
PY
```

2026-08-10 运行确认输出：

```text
IMPORTS=OK
TORCH=2.8.0+cu128
LEROBOT=0.6.2
LIBERO_RESET_OK
observation_keys: ['pixels', 'robot_state']
action_space: Box(-1.0, 1.0, (1, 7), float32)
cuda_available: True
GPU: NVIDIA GeForce RTX 4090
LIBERO_CLOSE_OK
```

Robosuite private-macro warning 不影响运行；环境 reset 和 close 已成功完成。

### 8. 记录已验证的远程环境

仅在全部远程检查通过后执行：

```bash
python -m pip freeze > ../results/training/remote_requirements_freeze.txt
nvidia-smi > ../results/training/remote_nvidia_smi.txt
git rev-parse HEAD > ../results/training/lerobot_commit.txt
```

此阶段不包含训练命令。

## 主要 RTX 6000D 服务器上的 Pi0.5 + LIBERO

> 执行边界：仅限远程 Linux GPU 服务器。
>
> 状态：2026-08-11 已在以下 LeRobot commit 完成运行验证：
> `22bd7a2f489b367d8df42de803b1e8c4ca63a3f9`.
> 真实 20-step forward/backward/optimizer sanity run 已通过。本节不构成长时间 fine-tuning 的执行授权。

### 已验证服务器与存储

- GPU：NVIDIA RTX 6000D，`nvidia-smi` 报告 85651 MiB。
- Driver：`595.71.05`；driver capability 报告 CUDA `13.2`。
- 持久化磁盘：`/root/autodl-tmp`，150 GB。
- 项目：`/root/autodl-tmp/VLA-Intern-Sprint`。
- Python 环境：`/root/autodl-tmp/miniforge3/envs/vla-intern`。

### 创建隔离 Runtime

```bash
source /etc/network_turbo
curl -fL --retry 5 --retry-delay 3 \
  -o /root/autodl-tmp/Miniforge3-Linux-x86_64.sh \
  https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
sha256sum /root/autodl-tmp/Miniforge3-Linux-x86_64.sh
bash /root/autodl-tmp/Miniforge3-Linux-x86_64.sh \
  -b -p /root/autodl-tmp/miniforge3

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
/root/autodl-tmp/miniforge3/bin/conda create -y -n vla-intern \
  python=3.12 ffmpeg=7.1.1 -c conda-forge
```

实测 installer SHA-256：

```text
848194851a98903134187fbb4ab50efe87b003e0c0f808f97644b7524a62bf2c
```

### 持久化环境变量

实际使用文件为 `/root/autodl-tmp/vla_env.sh`：

```bash
export VLA_ROOT=/root/autodl-tmp/VLA-Intern-Sprint
export HF_HOME=/root/autodl-tmp/cache/huggingface
export HF_HUB_CACHE=/root/autodl-tmp/cache/huggingface/hub
export HF_LEROBOT_HOME=/root/autodl-tmp/cache/huggingface/lerobot
export TORCH_HOME=/root/autodl-tmp/cache/torch
export PIP_CACHE_DIR=/root/autodl-tmp/cache/pip
export XDG_CACHE_HOME=/root/autodl-tmp/cache
export TMPDIR=/root/autodl-tmp/cache/tmp
export WANDB_DIR=/root/autodl-tmp/wandb
export MUJOCO_GL=egl
export VLA_PYTHON=/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python
```

### Clone 固定源码并安装已验证依赖集合

```bash
source /root/autodl-tmp/vla_env.sh
cd /root/autodl-tmp/VLA-Intern-Sprint/lerobot
git clone https://github.com/huggingface/lerobot.git .
git checkout --detach 22bd7a2f489b367d8df42de803b1e8c4ca63a3f9

/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python -m pip install \
  --index-url https://download.pytorch.org/whl/cu128 \
  torch==2.8.0 torchvision==0.23.0

/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python -m pip install \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  torchcodec==0.7.0 transformers==5.5.4 accelerate==1.14.0 hf-libero==0.1.4

cd /root/autodl-tmp/VLA-Intern-Sprint/lerobot
/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python -m pip install \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  -e ".[training,pi,libero]"

/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python -m pip check
```

当前源码中，Pi0.5 对应的 extra 是 `pi`。此前的 `.[training,smolvla,libero]` 命令属于历史 SmolVLA 环境配置，不是 Pi0.5 安装命令。

### 非交互配置 LIBERO

缺少 `~/.libero/config.yaml` 时，`hf-libero==0.1.4` 会在 stdin 交互询问。执行非交互环境初始化前先创建该配置：

```bash
mkdir -p /root/.libero /root/.cache/libero
ln -sfn /root/autodl-tmp/cache/libero-assets /root/.cache/libero/assets

printf '%s\n' \
  'assets: /root/autodl-tmp/cache/libero-assets' \
  'bddl_files: /root/autodl-tmp/miniforge3/envs/vla-intern/lib/python3.12/site-packages/libero/libero/bddl_files' \
  'datasets: /root/autodl-tmp/miniforge3/envs/vla-intern/lib/python3.12/site-packages/libero/libero/../datasets' \
  'init_states: /root/autodl-tmp/miniforge3/envs/vla-intern/lib/python3.12/site-packages/libero/libero/init_files' \
  > /root/.libero/config.yaml
```

### 已验证的验收命令

```bash
source /root/autodl-tmp/vla_env.sh
/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python \
  /root/autodl-tmp/VLA-Intern-Sprint/scripts/verify_remote_runtime.py

/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python \
  /root/autodl-tmp/VLA-Intern-Sprint/scripts/verify_libero_env.py

HF_HUB_OFFLINE=1 /root/autodl-tmp/miniforge3/envs/vla-intern/bin/python \
  /root/autodl-tmp/VLA-Intern-Sprint/scripts/verify_pi05_assets.py
```

### 已验证的 20-step Pi0.5 Sanity Training

```bash
source /root/autodl-tmp/vla_env.sh
bash /root/autodl-tmp/VLA-Intern-Sprint/scripts/run_pi05_sanity_new_server.sh
```

结果目录：

```text
/root/autodl-tmp/VLA-Intern-Sprint/results/training/pi05_sanity_new_server
```

最终 checkpoint：

```text
/root/autodl-tmp/VLA-Intern-Sprint/results/training/pi05_sanity_new_server/run/checkpoints/000020
```

不要在已有结果目录上重新执行该脚本；它会按设计拒绝覆盖已有运行。

## RTX 6000D 上的 Pi0.5 第一次正式实验

> 仅限远程 Linux。已于 2026-08-11 完成运行验证。这些命令创建了现有结果目录，并会主动拒绝覆盖。

### 固定配对评测协议

- Suite/task：`libero_10`，task ID `0`。
- 任务：`put both the alphabet soup and the tomato sauce in the basket`。
- 正式 seeds：`1000` 到 `1009`，每个 policy 10 episodes。
- Batch size 1、固定 initial states、hard reset、相对 7 维控制。
- 最大 520 control steps、`n_action_steps=10`、BF16 inference。
- 协议文件：`results/evaluation/eval_protocol.md`。

### Pretrained Pipeline Smoke 与正式基线

```bash
source /root/autodl-tmp/vla_env.sh
bash /root/autodl-tmp/VLA-Intern-Sprint/scripts/run_pi05_baseline_eval.sh
```

脚本先用 seed 999 运行一个不计入对比的 smoke episode；只有该 smoke 生成完整指标与视频后，才运行正式十集 baseline。

正式 baseline 结果：

```text
success=0/10
mean_episode_length=520.0
mean_model_inference_ms=181.6104
p95_model_inference_ms=221.9903
peak_allocated_gib=8.8700
peak_reserved_gib=9.1992
oom=false
```

### 第一阶段 2k Expert-only Training

```bash
source /root/autodl-tmp/vla_env.sh
bash /root/autodl-tmp/VLA-Intern-Sprint/scripts/run_pi05_first_stage_2k.sh
```

成功命令使用已验证的本地模型和数据集、batch size 1、policy/Accelerate BF16、expert-only training、冻结 vision encoder、gradient checkpointing、state/action mean/std normalization、2,000 steps、seed 1000 和 `save_freq=1000`。关闭 online evaluation、EMA、compile、W&B 和 Hub push。

Checkpoints：

```text
/root/autodl-tmp/VLA-Intern-Sprint/results/training/pi05_expert_first_stage_2k/run/checkpoints/001000
/root/autodl-tmp/VLA-Intern-Sprint/results/training/pi05_expert_first_stage_2k/run/checkpoints/002000
```

实测 scheduler scaling：warmup `1000 -> 66`，decay `30000 -> 2000`。

### 使用完全相同协议评测 2k Checkpoint

```bash
source /root/autodl-tmp/vla_env.sh
bash /root/autodl-tmp/VLA-Intern-Sprint/scripts/run_pi05_checkpoint_eval.sh
```

Checkpoint 结果：

```text
success=10/10
mean_episode_length=271.9
mean_model_inference_ms=168.9912
p95_model_inference_ms=208.3377
peak_allocated_gib=8.8700
peak_reserved_gib=9.1992
oom=false
```

### 在本地重新生成配对对比

复制小型结果产物（不包括 checkpoint）后在本地运行：

```powershell
python scripts/summarize_eval.py `
  --baseline-dir results/evaluation/pi05_pretrained_baseline `
  --checkpoint-dir results/evaluation/pi05_expert_first_stage_2k `
  --training-summary results/training/pi05_expert_first_stage_2k/torch_memory_timing_summary.json `
  --output-dir results/evaluation/pi05_first_comparison
```

没有新决策时不得启动 5k/10k training 或更大 LIBERO benchmark。当前对比只涉及一个任务，不是完整 LIBERO 分数。

## Pi0.5 Checkpoint 稳定性评测

> 仅限远程 Linux。已于 2026-08-11 成功执行。Runner 会拒绝覆盖两个已有结果目录。

### 用 10 Episodes 评测 1k，并以一次统一 30-Episode Run 评测 2k

```bash
source /root/autodl-tmp/vla_env.sh
bash /root/autodl-tmp/VLA-Intern-Sprint/scripts/run_pi05_checkpoint_stability_eval.sh
```

2k evaluation 被有意重新执行成一个不间断的 30-episode 进程。单独启动 `additional 20` 进程会让 LeRobot 固定 `init_state_id` 重置为 0，从而重复存储 initial state。

成功输出目录：

```text
/root/autodl-tmp/VLA-Intern-Sprint/results/evaluation/pi05_checkpoint_001000
/root/autodl-tmp/VLA-Intern-Sprint/results/evaluation/pi05_checkpoint_002000_30ep
```

实测结果：

```text
checkpoint 001000: 9/10, mean length 290.0, median 273.0, no OOM
checkpoint 002000: 28/30, mean length 291.1333, median 266.5, no OOM
```

### 测量 Seed 与存储 Init-State 的关系

```bash
source /root/autodl-tmp/vla_env.sh
/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python \
  /root/autodl-tmp/VLA-Intern-Sprint/scripts/analyze_libero_seed_init.py \
  --output /root/autodl-tmp/VLA-Intern-Sprint/results/evaluation/pi05_checkpoint_progression/seed_initial_state_evidence.json
```

实测结果：两个新环境都从固定 init-state row 0 开始，只把 seed 从 1000 改成 1010 时，首个 observation 完全相同。连续 row 0 和 1 的场景 pixels 与 robot state 不同。该任务包含 50 个唯一存储 row，30-episode run 使用的 row 0–29 也全部唯一。

### 为失败视频生成 Contact Sheet

```bash
/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python \
  /root/autodl-tmp/VLA-Intern-Sprint/scripts/make_eval_contact_sheets.py \
  --video /root/autodl-tmp/VLA-Intern-Sprint/results/evaluation/pi05_checkpoint_001000/videos/eval_episode_4.mp4 \
  --video /root/autodl-tmp/VLA-Intern-Sprint/results/evaluation/pi05_checkpoint_002000_30ep/videos/eval_episode_14.mp4 \
  --video /root/autodl-tmp/VLA-Intern-Sprint/results/evaluation/pi05_checkpoint_002000_30ep/videos/eval_episode_18.mp4 \
  --output-dir /root/autodl-tmp/VLA-Intern-Sprint/results/evaluation/pi05_checkpoint_progression/failure_contact_sheets
```

最终报告目录：

```text
results/evaluation/pi05_checkpoint_progression/
```

决策：保留 checkpoint 002000，在增加训练步数前选择有意义的 generalization test。没有新指令时不得启动 5k/10k training 或新 Rollout。

## Phase 1 新增评测固定初态

> 仅限远程 Linux。已于 2026-08-11 成功执行。Exposure audit 表明 40 个 dataset tasks 全部参与 2k fine-tuning 后，没有运行 cross-task Rollout。

### 不运行 Episode Rollout，仅验证指定 Fixed-State 范围

```bash
source /root/autodl-tmp/vla_env.sh
/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python - <<'PY'
from lerobot.envs.factory import make_env, make_env_config

cfg = make_env_config(
    "libero",
    task="libero_10",
    task_ids=[0],
    init_states=True,
    hard_reset=True,
    control_mode="relative",
    max_parallel_tasks=1,
)
vec = make_env(cfg, n_envs=1, use_async_envs=False)["libero_10"][0]
base = vec.envs[0].unwrapped
print({"before": base.init_state_id, "count": len(base._init_states)})
base.init_state_id = 30
print({"after": base.init_state_id, "requested_end": 49})
vec.close()
PY
```

实测：`before=0`、`count=50`、`after=30`、`requested_end=49`。

### 在 Init-State ID 30–49 上运行 Checkpoint 002000

```bash
source /root/autodl-tmp/vla_env.sh
bash /root/autodl-tmp/VLA-Intern-Sprint/scripts/run_pi05_heldout_init_eval.sh
```

成功输出：

```text
/root/autodl-tmp/VLA-Intern-Sprint/results/evaluation/generalization/heldout_initial_states
```

实测结果：

```text
init_state_ids=30-49
episodes=20
success=18/20
mean_episode_length=304.35
median_episode_length=282.0
mean_model_inference_ms=172.3727
p95_model_inference_ms=217.4534
peak_allocated_gib=8.8700
peak_reserved_gib=9.1992
oom=false
```

Wrapper 现在支持 `--init-state-start`，默认值仍为 0。它在第一次 reset 前设置现有同步环境对象的 `init_state_id`，并在每个 episode 中记录实际目标 ID。未修改 LeRobot/LIBERO 上游源码。

### Cross-Task 命令状态

没有执行 cross-task evaluation 命令。实际训练命令使用 `lerobot/libero` 全部 40 tasks 且无 task filter，因此同一数据集中没有任务符合原定 `unseen-to-this-finetuning` 对比要求。

## Phase 1 收尾：在本地重新生成 README 图表

> 仅限本地 Windows。这是纯 CPU 文档步骤，不运行 training、Rollout、Evaluation、模型推理或任何远程 GPU 工作负载。

```powershell
cd E:\VLA-Intern-Sprint
python scripts\generate_readme_figures.py
```

脚本读取已保存的 Phase 1 CSV/JSON/JSONL 产物，重新生成 `assets/figures/` 下五个 SVG。Training-loss 图在对数 y 轴上绘制全部 2,000 个原始 loss，不做平滑或人工插值。

## Phase 2 / Step 3：Isaac Observation 到 Pi0.5 Action Chunk

> 仅限 RTX 6000D 远程 Linux 执行。该命令只采集静止观测并运行推理；不会创建 VLA `/joint_command` publisher、不会调用控制器、不会执行 Action Chunk。

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint
bash phase2/scripts/run_phase2_step3_inference.sh
```

由于 AutoDL SSH 入口曾重置，最终运行采用脱离 SSH 的同一 wrapper：

```bash
RESULT=/root/autodl-tmp/VLA-Intern-Sprint/results/phase2_step3
nohup bash /root/autodl-tmp/VLA-Intern-Sprint/phase2/scripts/run_phase2_step3_inference.sh \
  > "$RESULT/run.log" 2>&1 < /dev/null &
echo $! > "$RESULT/wrapper.pid"
```

首次 policy-only 尝试因单样本嵌套四元数缺少 batch 维而被官方 `LiberoProcessorStep` 拒绝；失败日志保存在 `policy_inference_attempt1_missing_batch.log`。修复仅增加 batch 维，不改变数值或语义。最终对已经保存的同一真实静止观测执行：

```bash
bash /root/autodl-tmp/VLA-Intern-Sprint/phase2/scripts/run_phase2_step3_policy_only.sh
```

最终实测：3 次真实 `predict_action_chunk`，延迟分别为 407.157、186.766、186.218 ms；每次 shape 为 `[1,50,7]`，全部 finite；Torch peak allocated/reserved 为 8.870/9.201 GiB，OOM=false。完整证据位于 `results/phase2_step3/`。
## Phase 2 / Step 4：Action Adapter 与单动作执行

> 仅允许在 RTX 6000D 远程 Linux 执行。正式成功流程严格要求合成安全门先 PASS；随后只调用一次 Pi0.5，并只执行 `action_chunk[0]`。

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint

# Gate 1：不加载 Pi0.5，只运行小幅 synthetic translation/orientation/gripper。
bash phase2/scripts/run_phase2_step4_synthetic.sh

# Gate 2：Gate 1 PASS 后，一次 inference + 一个 action；不执行剩余49步。
bash phase2/scripts/run_phase2_step4.sh
```

Step 4 已完成，不要在现有结果目录上重复运行。最终结果位于 `results/phase2_step4/`，展示资产位于 `assets/images/phase2_step4_*.png` 与 `assets/videos/phase2_step4_action_execution.mp4`。

## Phase 2 / Step 5：五轮 Receding-Horizon 闭环

> 仅允许在 RTX 6000D 远程 Linux 执行。该命令已于 2026-08-12 成功运行，现有 wrapper 会拒绝覆盖完成的 `run_status.json`。不要重复执行，也不要把 Cycle 数改为大于 5。

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint

# Step 4 两个 gate 已 PASS 后：每轮新 Observation → 一次真实推理
# → 只执行 action_chunk[0] → 新 Observation，共严格 5 轮。
bash phase2/scripts/run_phase2_step5.sh
```

实际因 SSH 会话稳定性采用后台启动，执行内容仍是上面的同一个 wrapper：

```bash
bash /root/autodl-tmp/VLA-Intern-Sprint/phase2/scripts/restart_phase2_step5_after_attempt1.sh
```

只读验收：

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint
cat results/phase2_step5/run_status.json
cat results/phase2_step5/closed_loop_summary.json
cat results/phase2_step5/inference_latency.json
cat results/phase2_step5/safety_report.json
git -C lerobot status --short --branch
pgrep -af 'pi05_step5_policy_daemon|isaac_step5_closed_loop|run_phase2_step5' || true
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader
```

离线汇总命令（本地 CPU，不加载模型、不启动 Isaac）：

```powershell
cd E:\VLA-Intern-Sprint
python phase2\scripts\summarize_phase2_step5.py `
  --result-dir results\phase2_step5 `
  --video assets\videos\phase2_step5_closed_loop.mp4 `
  --start-image assets\images\phase2_step5_start.png `
  --end-image assets\images\phase2_step5_end.png
```

## Phase 3 / Step 6：已成功执行命令

> 仅 RTX 6000D 远程 Linux。以下命令已于 2026-08-12 实际执行完成；结果目录已有完成保护，不要原地重跑覆盖。

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint
source phase2/scripts/isaac_env.sh
source /root/autodl-tmp/vla_env.sh

bash phase3/scripts/audit_phase3_step6_libero.sh \
  > /root/autodl-tmp/phase3_step6_libero_audit.txt

PYTHONPATH="$PWD/lerobot/src" /root/autodl-tmp/miniforge3/envs/vla-intern/bin/python \
  phase3/scripts/capture_phase3_step6_libero_reference.py \
  --output-dir results/phase3_step6/libero_reference --init-state-id 0 --resolution 360
PYTHONPATH="$PWD/lerobot/src" /root/autodl-tmp/miniforge3/envs/vla-intern/bin/python \
  phase3/scripts/capture_phase3_step6_libero_reference.py \
  --output-dir results/phase3_step6/libero_reference_state01 --init-state-id 1 --resolution 256
PYTHONPATH="$PWD/lerobot/src" /root/autodl-tmp/miniforge3/envs/vla-intern/bin/python \
  phase3/scripts/capture_phase3_step6_libero_reference.py \
  --output-dir results/phase3_step6/libero_reference_state02 --init-state-id 2 --resolution 256

/root/autodl-tmp/isaac_sim/venv/bin/python \
  phase3/scripts/prepare_phase3_step6_assets.py \
  2>&1 | tee results/phase3_step6/asset_conversion.log

PYTHONPATH="$PWD/phase3/scripts" /root/autodl-tmp/isaac_sim/venv/bin/python \
  phase3/scripts/isaac_step6_scene_gate.py \
  --initial-state-id 0 --dynamic-objects \
  --output-dir results/phase3_step6/scene_gate_state00_dynamic \
  > results/phase3_step6/scene_gate_state00_dynamic.log 2>&1

# 唯一三回合正式实验：state 0/1/2、hard reset、MAX_CYCLES=100、K=1。
bash phase3/scripts/run_phase3_step6.sh \
  > results/phase3_step6/run_step6.log 2>&1

nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv,noheader
nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader
```

本地只做结果整理，不运行 VLA：

```powershell
cd E:\VLA-Intern-Sprint
python phase3\scripts\finalize_phase3_step6_artifacts.py
powershell -ExecutionPolicy Bypass -File phase3\scripts\make_phase3_step6_comparison.ps1
```
## Phase 3 / Step 7A：LIBERO → Isaac Action Parity（仅远程，已完成）

以下命令在 RTX 5090 远程服务器执行；不调用 Pi0.5、不训练、不做任务 rollout。每个 canonical action 独立启动 Isaac 场景并只执行约 0.05 秒控制周期：

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint
chmod +x phase3/scripts/run_phase3_step7_action_parity.sh
phase3/scripts/run_phase3_step7_action_parity.sh
```

结果目录：`/root/autodl-tmp/VLA-Intern-Sprint/results/phase3_step7/action_parity/`。

关键结果文件：`libero_all.json`、`libero_translation.json`、`isaac_translation.json`、`translation_comparison.json`、`libero_rotation.json`、`isaac_rotation.json`、`rotation_comparison.json`、`libero_gripper.json`、`isaac_gripper.json`、`gripper_comparison.json`、`parity_matrix.json`、`summary.md`、`run_status.json`。本地只读取和整理结果，不重建 VLA 运行环境。
## Phase 3 / Step 7A.1：Action Parity Mismatch Localization（仅远程/离线分析，已完成）

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint
/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python \
  phase3/scripts/localize_action_parity.py \
  --parity-dir results/phase3_step7/action_parity_attempt2 \
  --output-dir results/phase3_step7/action_parity_localization
```

该命令只读取已有 JSON，不启动 Isaac、LIBERO、Pi0.5、训练或 rollout。输出：`mismatch_table.json`、`target_translation_audit.json`、`target_rotation_audit.json`、`eef_reference_audit.json`、`tracking_audit.json`、`reset_audit.json`、`root_cause_candidates.json`、`run_status.json`、`summary.md`。
## Phase 3 / Step 7B: State Mapping / EEF Calibration Audit（仅远程；已完成）

以下两条采集命令只把五组明确 Panda 关节向量写入各自仿真器并读取状态；不调用 Pi0.5、不训练、不执行任务 action 或 Step 6 rollout。输出文件必须不存在，避免覆盖证据。

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint
source /root/autodl-tmp/vla_env.sh

PYTHONPATH="$PWD/lerobot/src" /root/autodl-tmp/miniforge3/envs/vla-intern/bin/python \
  phase3/scripts/capture_libero_state_calibration.py \
  --output results/phase3_step7/state_mapping_audit/libero_state_semantics.json

export PYTHONPATH="$PWD/phase3/scripts:$PWD/phase2/scripts"
source phase2/scripts/isaac_env.sh
/root/autodl-tmp/isaac_sim/venv/bin/python \
  phase3/scripts/capture_isaac_state_calibration.py \
  --output results/phase3_step7/state_mapping_audit/isaac_state_semantics.json
```

以下命令为纯离线 JSON 分析，不导入或启动 Isaac、LIBERO、Pi0.5；完成目录上重新执行会拒绝覆盖：

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint
/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python \
  phase3/scripts/analyze_state_mapping_calibration.py \
  --libero results/phase3_step7/state_mapping_audit/libero_state_semantics.json \
  --isaac results/phase3_step7/state_mapping_audit/isaac_state_semantics.json \
  --output-dir results/phase3_step7/state_mapping_audit
```

已完成的正式输出：`five_pose_calibration.json`、`tool_offset_audit.json`、`orientation_calibration.json`、`gripper_state_audit.json`、`timestamp_audit.json`、`state_parity_matrix.json`、`root_cause_candidates.json`、`frame_tree.json`、`run_status.json`、`summary.md`。早期分析尝试保存在独立 `state_mapping_audit_attempt*` 目录；不作为正式结论输入。
## Phase 3 / Step 7B.1：状态映射修复与静态复核（仅远程，已完成）

以下命令只使用既有 ten-pose JSON 和 CPU Python 进行复核；不导入 Isaac、Pi0.5 或 LIBERO，不执行训练、任务 rollout 或 Step 6 重跑。脚本拒绝覆盖已经存在的证据文件。

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint
export PYTHONPATH="$PWD/phase3/scripts"

/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python \
  phase3/scripts/test_state_mapping_adapter.py

/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python \
  phase3/scripts/validate_state_mapping_fix.py \
  --input-dir results/phase3_step7/state_mapping_fix \
  --output-dir results/phase3_step7/state_mapping_fix

for f in before_fix.json position_transform.json orientation_transform.json \
  gripper_mapping.json calibration_5_pose_before_after.json \
  holdout_5_pose_validation.json position_error_summary.json \
  orientation_error_summary.json gripper_validation.json run_status.json; do
  /root/autodl-tmp/miniforge3/envs/vla-intern/bin/python -m json.tool \
    "results/phase3_step7/state_mapping_fix/$f" >/dev/null
done

nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader
```

实际结果：夹爪单元测试通过，10 个 JSON 均可解析；RTX 5090 最终为 `0 MiB / 0%`。本轮位置候选使用 USD 原生 `/World/Robot/panda_hand/tool_center`，而不是拟合 world-space 常数偏移；夹爪输入从 `[finger1, finger2]` 映射为 `[finger1, -finger2]`。姿态和 `0.15 s` timestamp skew 均未修改。
## Phase 3 / Step 7C：Scripted Grasp Oracle（仅远程，已完成）

脚本先运行一次 `DIAGNOSTIC / NOT COUNTED`，确认 top-down 几何；随后只运行固定的六次正式试验，每次独立 hard reset，不追加重试：

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint
source phase2/scripts/isaac_env.sh
export PYTHONPATH="$PWD/phase2/scripts:$PWD/phase3/scripts"

# 仅诊断，不计入正式统计
bash phase3/scripts/run_phase3_step7_grasp_oracle_diagnostic.sh

# 正式协议：alphabet_00..02 + tomato_00..02，共 6 次
bash phase3/scripts/run_phase3_step7_grasp_oracle.sh
```

实际远程结果：alphabet soup `3/3`；tomato sauce `0/3`，三次均在 descent 阶段 `SAFETY_STOP`；总体 `3/6`，判定 `PARTIAL`。未调用 Pi0.5 / `predict_action_chunk`，未训练，未重跑 Step 6，未 teleport 物体、attach 物体或修改物理参数。六个真实视频：`assets/videos/phase3_step7_oracle_alphabet_00.mp4`、`_01.mp4`、`_02.mp4`、`phase3_step7_oracle_tomato_00.mp4`、`_01.mp4`、`_02.mp4`。最终 RTX 5090：`0 MiB / 0%`。

## Phase 3 / Step 7C.1：Tomato Safety-Stop 静态定位（本地只读，已完成）

以下命令只读取冻结的 Step 7C 文件和源码，不启动 Isaac、Pi0.5、训练、rollout 或 GPU 任务：

```powershell
cd E:\VLA-Intern-Sprint

Get-Content -Raw phase3\scripts\isaac_step7_grasp_oracle.py
Get-Content -Raw results\phase3_step7\grasp_oracle\tomato_00\exception.txt
Get-Content -Raw results\phase3_step7\grasp_oracle\tomato_01\exception.txt
Get-Content -Raw results\phase3_step7\grasp_oracle\tomato_02\exception.txt

Get-ChildItem results\phase3_step7\grasp_oracle\tomato_*\video_frames -File
Get-FileHash -Algorithm SHA256 results\phase3_step7\grasp_oracle\tomato_*\exception.txt
```

静态结论：三次均定位到 `descent step 0` 的聚合安全门；精确 leaf（non-finite / joint delta / lower limit / upper limit）因原始异常路径未落盘遥测而保持 `UNRESOLVED_FROM_EXISTING_LOGS`。本轮没有执行任何远程命令，也没有应用建议中的诊断代码修改或新增 trial。

## Phase 3 / Step 7C.2：Tomato Safety Telemetry Diagnostic（仅远程，已完成）

唯一一次 `DIAGNOSTIC / NOT COUNTED` 运行命令：

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint
bash phase3/scripts/run_phase3_step7_tomato_safety_diagnostic.sh
```

运行入口拒绝覆盖 `results/phase3_step7/tomato_safety_diagnostic/`，因此该命令不能在当前目录上重复执行。实际退出码为 `0`，只执行一次 tomato diagnostic，未运行正式 trial、Pi0.5、训练或 Step 6。

实际触发：`descent step 0` 的 `JOINT_UPPER_LIMIT`。`panda_finger_joint2` target=`0.04000000283122063 rad`，runtime upper=`0.03999999910593033 rad`，excess=`3.725290298461914e-09 rad`。PINK target 全部 finite；最大 joint delta 为 `panda_joint6` 的 `0.04410219192504883 rad`，未超过保持不变的 `0.05 rad` 阈值；无 lower-limit violation。

原 Step 7C 汇总和三个 tomato 正式 `result.json` 在运行前后的 SHA-256 一致；诊断结束后 RTX 5090 为 `0 MiB`。本轮只定位，不应用数值容差修复。

## Phase 3 / Step 7C.3：Floating-Point-Safe Safety Fix 与 Tomato Post-Fix Oracle

仅远程执行。先运行不启动 Isaac 的纯数值单元测试；只有正式结果为 `all_pass=true` 后才运行固定三次 Tomato trial：

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint
bash phase3/scripts/run_phase3_step7_safety_unit_tests.sh

source phase2/scripts/isaac_env.sh
export PYTHONPATH="$PWD/phase2/scripts:$PWD/phase3/scripts"
bash phase3/scripts/run_phase3_step7_tomato_postfix.sh
```

静态生成汇总（不会启动 Isaac，也不会增加 trial）：

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint
python phase3/scripts/summarize_phase3_step7_tomato_postfix.py \
  --result-dir results/phase3_step7/tomato_oracle_postfix
```

实际结果：单元测试最终 `13/13 PASS`；固定三次 trial 均在 descent step 0 通过项目 Safety 并记录 float-tolerance clamp，随后均因 PINK 内部 configuration-limit 检查返回 `IK_FAILURE`。Tomato AFTER=`0/3`，Step 7C.3=`PARTIAL`。没有第 4 次、Alphabet 重跑或第二个自动修复。

## Phase 3 / Step 7C.4：PINK Finger-Joint Configuration Limit 静态审计

本阶段只读源码和已有结果，不启动 Isaac。关键本地检查：

```powershell
cd E:\VLA-Intern-Sprint

Get-Content -Encoding UTF8 phase3\scripts\phase3_step6_common.py
Get-Content -Encoding UTF8 phase3\scripts\isaac_step6_scene_gate.py
Get-Content -Encoding UTF8 phase3\scripts\isaac_step7_grasp_oracle.py
Get-Content -Encoding UTF8 results\phase3_step7\tomato_oracle_postfix\trial_00\descent_step0.json
Get-Content -Encoding UTF8 results\phase3_step7\tomato_safety_diagnostic\joint_telemetry.json
```

仅远程只读检查实际安装源码：

```bash
P=/root/autodl-tmp/isaac_sim/venv/lib/python3.12/site-packages/isaacsim/exts/isaacsim.robot_motion.pink

nl -ba "$P/isaacsim/robot_motion/pink/impl/pink_ik_controller.py"
nl -ba "$P/isaacsim/robot_motion/pink/impl/configuration_loader.py"
nl -ba "$P/isaacsim/robot_motion/pink/impl/utils/transforms.py"
nl -ba "$P/pip_prebundle/pink/configuration.py"
nl -ba "$P/pip_prebundle/pink/tasks/posture_task.py"
nl -ba "$P/robot_configurations/franka/robot.urdf"
```

静态结论：PINK configuration/QP 包含 7 arm + 2 finger；index 8 确认是 prismatic `panda_finger_joint2`。失败值来自 solve 前的 Isaac current q，PINK 使用 `1e-6 m` tolerance 在 QP 构建前拒绝。没有运行修复或诊断 trial。
## Phase 3 / Step 7C.5：Arm / Gripper IK 解耦（仅远程，已完成）

以下是本次实际执行记录。运行器包含不可覆盖门禁，且本阶段只授权过一次 diagnostic；**不要再次执行该运行器**。

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint

# Isaac 启动前的纯 CPU Safety 回归：13/13 PASS
PYTHONPATH=phase3/scripts \
  /root/autodl-tmp/miniforge3/envs/vla-intern/bin/python \
  phase3/scripts/test_joint_safety_float_limits.py \
  --output results/phase3_step7/arm_gripper_decoupling/safety_regression_13_cases.json

# Isaac 启动前的 7D 架构与 mapping A-G 测试
PINK=/root/autodl-tmp/isaac_sim/venv/lib/python3.12/site-packages/isaacsim/exts/isaacsim.robot_motion.pink
PRE="$PINK/pip_prebundle"
export PYTHONPATH="$PWD/phase3/scripts:$PRE:$PRE/cmeel.prefix/lib/python3.12/site-packages"
export LD_LIBRARY_PATH="$PRE/cmeel.prefix/lib:${LD_LIBRARY_PATH:-}"
/root/autodl-tmp/isaac_sim/venv/bin/python \
  phase3/scripts/test_arm_gripper_decoupling.py \
  --urdf "$PINK/robot_configurations/franka/robot.urdf" \
  --result-dir results/phase3_step7/arm_gripper_decoupling \
  --safety-results results/phase3_step7/arm_gripper_decoupling/safety_regression_13_cases.json

# 历史实际运行命令：只执行过一次，DIAGNOSTIC / NOT COUNTED
bash phase3/scripts/run_phase3_step7_arm_gripper_decoupling.sh
```

只读验收：

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint
python -m json.tool results/phase3_step7/arm_gripper_decoupling/unit_tests.json >/dev/null
python -m json.tool results/phase3_step7/arm_gripper_decoupling/trial_result.json >/dev/null
python -m json.tool results/phase3_step7/arm_gripper_decoupling/run_status.json >/dev/null
diff -u \
  results/phase3_step7/arm_gripper_decoupling/frozen_assets_before.sha256 \
  results/phase3_step7/arm_gripper_decoupling/frozen_assets_after.sha256
nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader
```

实际结果：A–H 全部 PASS；唯一 diagnostic 的 exit code 为 0，PINK runtime 为 7D，descent 完成至 step 199，close/lift 完成，最大/最终竖直位移为 `146.531/145.893 mm`。原 finger configuration-limit 错误未再出现；Pi0.5、训练和 Step 6 均未运行。历史正式 Tomato 仍为 `0/3`。
## Phase 3 / Step 7C.6：Tomato 固定协议解耦后验证（仅远程，已完成）

本阶段严格运行 3 个正式 trial，不得再次执行以下 trial 循环，也不得增加第 4 次。

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint
source phase2/scripts/isaac_env.sh
export PYTHONPATH="$PWD/phase2/scripts:$PWD/phase3/scripts${PYTHONPATH:+:$PYTHONPATH}"

# 运行前：冻结 Oracle、Safety、scene、配置、7D URDF 和安装的 PINK controller 哈希。
sha256sum \
  phase3/scripts/isaac_step7_grasp_oracle.py \
  phase3/scripts/joint_safety_float_limits.py \
  phase3/scripts/isaac_step6_scene_gate.py \
  phase3/scripts/phase3_step6_common.py \
  phase3/scripts/pink_arm_only.py \
  results/phase3_step7/arm_gripper_decoupling/franka_arm_only.urdf \
  /root/autodl-tmp/isaac_sim/venv/lib/python3.12/site-packages/isaacsim/exts/isaacsim.robot_motion.pink/isaacsim/robot_motion/pink/impl/pink_ik_controller.py \
  > results/phase3_step7/tomato_oracle_validation/code_hashes_before.sha256

# 历史实际执行：固定 00/01/02，均为独立 hard reset；不要再次执行。
for index in 0 1 2; do
  folder="results/phase3_step7/tomato_oracle_validation/trial_$(printf '%02d' "$index")"
  /root/autodl-tmp/isaac_sim/venv/bin/python \
    phase3/scripts/isaac_step7_grasp_oracle.py \
    --object tomato \
    --trial-index "$index" \
    --arm-only-urdf results/phase3_step7/arm_gripper_decoupling/franka_arm_only.urdf \
    --output-dir "$folder"
done
```

只读验收：

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint
diff -u \
  results/phase3_step7/tomato_oracle_validation/code_hashes_before.sha256 \
  results/phase3_step7/tomato_oracle_validation/code_hashes_after.sha256

python -m json.tool results/phase3_step7/tomato_oracle_validation/trial_summary.json >/dev/null
python -m json.tool results/phase3_step7/tomato_oracle_validation/run_status.json >/dev/null
sha256sum -c results/phase3_step7/tomato_oracle_validation/video_hashes.sha256
nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader
```

实际结果：Safety regression `13/13 PASS`；Tomato validation 00/01/02 均为 SUCCESS，正式 after=`3/3`。三次 PINK 均为 7D，descent 200/200，Safety/IK/finger-limit failure 均为 0；最大/最终竖直位移均为 `146.531/145.893 mm`。代码/配置哈希 diff 为 0 字节。Pi0.5、训练和 Step 6 均未运行。
## Phase 3 / Step 7D：一次性 Pi0.5 修复后诊断（仅远程，已执行；禁止重跑）

以下命令在 RTX 5090 上只执行过一次。结果为 100 cycles / HORIZON_REACHED，**不得再次执行该运行器**：

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint
bash phase3/scripts/run_phase3_step7d.sh
```

只读验收命令：

```bash
cd /root/autodl-tmp/VLA-Intern-Sprint

python -m json.tool results/phase3_step7/pi05_postfix_diagnostic/run_status.json
python -m json.tool results/phase3_step7/pi05_postfix_diagnostic/trial_result.json
python -m json.tool results/phase3_step7/pi05_postfix_diagnostic/before_after_comparison.json
python -m json.tool results/phase3_step7/pi05_postfix_diagnostic/checkpoint_hash.json
python -m json.tool results/phase3_step7/pi05_postfix_diagnostic/policy_handshake_reconciliation.json

sha256sum assets/videos/phase3_step7_pi05_postfix_diagnostic_state0.mp4
nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits
ps -eo pid,cmd | grep -E '[i]saac|[p]i05_step7d' || true
```

实际 checkpoint：

```text
/root/autodl-tmp/VLA-Intern-Sprint/results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model
model.safetensors SHA-256 = 590c83ba6061fbfeb887d675deb9b173bbe23f65722c6b38ce242825ffbac631
```

注意：原始 `policy_complete.json` 保留了最后一轮文件握手竞态；结合 100 个真实 policy response、100 个已完成 cycle、Isaac exit code 0 和完整 `episode_complete.json`，离线协调记录为 `policy_handshake_reconciliation.json`。不要据此重跑 episode。
