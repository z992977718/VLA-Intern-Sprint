# 命令记录

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
