# 每日记录

## 2026-08-13：Phase 3 / Step 7 Stage A 全栈迁移门禁

- 按 Step 7 授权，仅启动新的 RTX 5090 Stage A 最小全栈验证；未训练、未运行 Step 6、未覆盖历史 checkpoint/evaluation/video。
- 初始 Stage A attempt 因固定 150 秒等待以及 `set -u` 下 source ROS setup 的 shell 兼容问题退出；均保留为独立历史证据，不是 GPU 或 Isaac 功能失败。
- 无固定门限的分层诊断确认：基础 Isaac 冷启动约 110 秒；单相机、双相机读帧和 ROS2 bridge-only 都通过。原日志末尾的 `isaacsim.sensors.experimental` 不是已确认卡点。
- Stage A attempt03=PASS：Vulkan、Isaac RaytracedLighting、ROS2 Humble、两路 256x256 RGB、`/joint_states`、fresh Observation、PINK、一次真实 2k Pi0.5 action chunk 和仅 index 0 的实际动作均通过；无 OOM、无 dtype/device mismatch、无 task rollout。
- Pi0.5 输出 `[1,50,7]`、finite，单次 smoke 调用 741.562 ms，Torch peak allocated/reserved 约 8.87/9.20 GiB；机器人实际移动，目标位置误差 1.099 mm、姿态误差 6.517 mrad。该调用不是正式 profiling benchmark。
- 这次 image-to-joint 近似时间配对最大 skew 为 0.15 秒，需作为后续 state/camera 对齐审计限制记录。RTX 5090 全栈迁移已排除为 Step 6 0/3 的直接原因；Step 7 后续根因仍未隔离。

## 2026-08-13：RTX 6000D → RTX 5090 克隆迁移审计

- 新服务器入口为 `ssh -p 22705 root@connect.westd.seetacloud.com`；旧实验资产未重跑、未覆盖。
- RTX 5090：32,607 MiB VRAM，driver 580.105.08，PyTorch 2.8.0+cu128，CUDA runtime 12.8，compute capability 12.0，BF16 可用。
- 项目专用 Python `/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python`、`/root/autodl-tmp/vla_env.sh`、LeRobot commit `22bd7a2f489b367d8df42de803b1e8c4ca63a3f9` 均仍有效。
- 已确认 1k/2k checkpoint、训练原始日志、evaluation summaries、LIBERO metadata/cache、Phase 2/3 结果和视频存在；本地有 `assets/figures`，远程克隆目录未找到该目录，未重生成图表。
- 执行独立 `scripts/check_5090_migration.py`，输出到新目录 `results/migration_smoke_5090_20260813/`。真实 LIBERO `libero_10` task 0 reset 后，使用 LeRobot 实际 processor 和 2k Pi0.5 checkpoint 完成一次 `predict_action_chunk`。
- Smoke 结果：两路 `[1,3,360,360]` 图像、`[1,8]` state、语言 token 均进入 `cuda:0`；输出 `[1,50,7]` float32、全 finite；OOM=NO；未执行环境 action；peak allocated/reserved 约 8.87/9.20 GiB；单次 556.762 ms（仅迁移 smoke，不是正式 benchmark）。
- 结论：迁移成功，无 GPU/BF16/dtype/device/OOM 阻塞。若继续，优先在独立目录做 RTX 5090 warm-up 后多次 inference profiling，不启动训练或新的任务评测。

## 2026-08-12 — Phase 2 / Step 2 Camera + Observation：PASS

- 初次运行因系统 ICD 指向 `libGLX_nvidia.so.0` 出现 `ERROR_INCOMPATIBLE_DRIVER`；原始失败证据归档为 `results/phase2_step2/attempt_001_glx_icd_failure/`，没有覆盖或伪造。
- 按 AutoDL 官方 headless Vulkan 方案安装 `vulkan-tools/libvulkan1/libsm6/libegl1`，新增独立 `my_nvidia_icd.json` 指向 `libEGL_nvidia.so.0`；没有覆盖系统原 ICD，也没有修改 NVIDIA Driver 或 CUDA。
- `vulkaninfo --summary` 实测退出码 0，识别 `PHYSICAL_DEVICE_TYPE_DISCRETE_GPU`、`NVIDIA RTX 6000D`、driver `595.71.05`。
- 两路 `RtxCamera + CameraSensor + ROS2PublishImage` 均发布 256×256 `rgb8`；`/joint_states` 同时可用，Observation Adapter 退出码 0。
- 外部相机像素标准差 61.13、暗像素占比 0.182%；第二路手腕跟随视角像素标准差 48.94、暗像素占比 0.116%，人工检查均为真实有效画面。
- 第二路不是已标定刚性 eye-in-hand 外参：Camera prim 位于 `/World/WristTrackingCamera`，每帧跟随 `panda_hand` 的世界位置并看向手腕前下方工作区。该限制已写入元数据。
- 最终 Attempt 007：`node_exit=0`、`missing=[]`、`invalid_frames=[]`、峰值显存 3265 MiB、无 OOM；图像与 joint-state 最大时间戳差 0.05 秒。
- 已生成两张 PNG、camera/joint/timing metadata、Observation Snapshot、ROS topic 证据、GPU 时序与运行日志；完成后无 Isaac 进程、GPU 无计算任务。
- `policy_loaded=false`、`vla_action_sent=false`；未加载 Pi0.5、未执行 inference/control、未进入 Step 3。

## 2026-08-12 — Phase 2 / Step 2 首次尝试：FAIL（历史记录，后续已修复）

- 冻结 Step 1，未重新安装 Isaac/ROS 2，未启动 Pi0.5、训练、Rollout、Evaluation 或 VLA 控制。
- 从固定 dataset metadata、LeRobot 0.6.2 源码和实际评测配置确认 Phase 1 schema：两路 RGB；`observation.state=[eef_pos(3), eef_axisangle(3), gripper_qpos(2)]`；相对 OSC_POSE action 7 维；语言经 complementary `task` 进入 Pi0.5 processor。
- 确认图像三层尺寸：dataset 256×256；Phase 1 Rollout 环境 360×360；Pi0.5 processor 最终 resize-with-pad 到 224×224 并映射到 `[-1,1]`。
- Isaac `/joint_states` 实测为 7 个 arm joint + 2 个 finger joint，position/velocity/effort 各 9 维；与 LIBERO 8 维 state 在维度和语义上均不兼容。
- 在项目自有 ROS 2 package 新增 `observation_adapter_node`，按 joint name 建立映射，计划订阅 external/wrist 两路 RGB、保存 PNG/JSON 和时间差；包编译成功。
- 按 Isaac Sim 6.0.1 官方当前接口实现两路 `RtxCamera(tick_rate=10)` + `CameraSensor` + `ROS2PublishImage`，未使用 deprecated `frameSkipCount`。
- 真实远程运行中，Franka 和 `/joint_states` 可发现，但两路 Image topic 均未创建。日志明确出现 `ERROR_INCOMPATIBLE_DRIVER`、`GPU Foundation is not initialized!`、`IHydraTexture refResource had no GPU foundation`。
- 容器 CUDA/Warp 可见 RTX 6000D，但无 `/dev/nvidia-modeset`；NVIDIA 文档要求容器创建时提供 `graphics` capability 才能运行 Vulkan。进程内无法补做宿主机驱动挂载。
- 运行峰值显存 577 MiB，无 OOM；最终没有 Isaac/Adapter 进程残留。
- 没有生成或伪造 PNG、camera metadata、timing 或 Observation Snapshot。
- 当时结论为 **FAIL**；随后同日通过 AutoDL headless EGL ICD 方案修复并完成 Attempt 007 PASS。此段只保留首次失败历史，不代表当前状态。

## 2026-08-12 — Phase 2 / Step 1 完成

- 冻结 Phase 1 结果，未启动 Pi0.5、LIBERO、训练、Rollout 或 Evaluation。
- 根据 NVIDIA 当前官方文档选择 Isaac Sim 6.0.1；服务器为 Ubuntu 22.04.5、Driver 595.71.05、RTX 6000D 85,651 MiB、1 TiB RAM。
- 在 `/root/autodl-tmp/isaac_sim/venv` 创建独立 Python 3.12 环境；使用数据盘缓存，最终数据盘约 63 GiB 可用。
- 安装 ROS 2 Humble ros-base 并通过 `ros2 doctor --report`；构建 `vla_manipulator_runtime`。
- 默认 Isaac base experience 的拆包依赖需要额外官方 asset/cortex/replicator/test/example 包；未修改 NVIDIA upstream。
- 修正 Isaac 内置 Humble `LD_LIBRARY_PATH` 后，ROS 2 Bridge 成功加载内部 rclpy。
- Isaac Sim 6.0.1 headless application 启动、官方 Franka 6.0 USD 加载到 `/panda`，physics 正常运行；当时配置请求了 RaytracedLighting，但没有做图像验收。Step 2 追溯日志后确认同次运行已存在 Vulkan GPU Foundation 错误，因此不能把 RTX rendering 称为 PASS。
- `/joint_states` 与 `/joint_command` 均被 ROS 2 发现，消息类型为 `sensor_msgs/msg/JointState`。
- 最终一键复现中，七轴关节从 `[0.012,-0.5686,0,-2.8109,0,3.0368,0.741]` 移动到 `[0.0001,-0.4489,0,-1.7715,0,1.3560,0.7796]`，目标最大误差 0.0560 rad；闭环节点退出码 0。
- 最终成功一键复现保存 23 个 GPU 采样点，peak VRAM 为 577 MiB，无 OOM；完成后 Isaac 已停止，GPU 回到 0 MiB。
- Remote visualization 未配置；保留关节状态数值证据，没有声称存在截图或视频。
- Phase 2 / Step 1：PASS。停止并等待 Step 2 指令。

## 2026-08-10——远程环境静态核验

### 范围

- 只检查源码与文档；
- 未在本地 Windows/WSL 安装或 import 训练依赖；
- 未在本地初始化 LIBERO；
- 未运行训练、Rollout、Evaluation 或 GPU profiling；
- 未修改官方 `lerobot/` 源码树。

### 已检查的 LeRobot 版本

- Commit：`22bd7a2f489b367d8df42de803b1e8c4ca63a3f9`
- Commit 日期：`2026-08-07`
- Commit 标题：`chore: sort imports in vla_jepa tests (#4354)`
- `pyproject.toml` package version：`0.6.2`
- 检查时 Git 状态：detached HEAD，worktree 干净。

### 已确认环境要求

- 远程 OS 必须为 Linux；`libero` extra 只在 `sys_platform == 'linux'` 时安装 `hf-libero`。
- Python：`>=3.12`；文档选择 Python 3.12。
- 核心依赖范围：`torch>=2.7,<2.12.0`、`torchvision>=0.22.0,<0.27.0`。
- Training extra：dataset dependencies、Accelerate、Weights & Biases。
- SmolVLA extra：Transformers、num2words、Accelerate。
- LIBERO extra：dataset、Transformers、SciPy、Linux 下的 `hf-libero>=0.1.4,<0.2.0`。
- 当时确认的最小组合安装：`python -m pip install -e ".[training,smolvla,libero]"`。
- 文档中的 CUDA 12.8 wheels 要求 NVIDIA driver 至少为 `570.86`；当时远程 driver/GPU 尚未验证。
- LIBERO 使用 MuJoCo；无界面服务器应设置 `MUJOCO_GL=egl`。
- 官方 LIBERO Dockerfile 会预下载 `lerobot/libero-assets` 并写入 `~/.libero/config.yaml`，以避免首次 import 交互。
- 真实 LIBERO 验收必须执行 `reset()`，因为底层 `OffScreenRenderEnv` 在 reset 时才延迟创建。

### 已检查证据

- `lerobot/pyproject.toml`
- `lerobot/docs/source/installation.mdx`
- `lerobot/docs/source/smolvla.mdx`
- `lerobot/docs/source/libero.mdx`
- `lerobot/docker/Dockerfile.benchmark.libero`
- `lerobot/src/lerobot/envs/libero.py`
- `lerobot/.github/workflows/benchmark_tests.yml`

### 验证状态

- 本地静态核验：完成；
- 远程 SSH key 登录：通过；
- 远程 `torch`、`lerobot`、`libero` import：通过；
- 远程 PyTorch：`2.8.0+cu128`；LeRobot：`0.6.2`；
- 远程 CUDA：NVIDIA GeForce RTX 4090（24 GB）可用，driver `580.105.08`；
- `lerobot/libero-assets`：完整下载 `586/586` 至 `/root/autodl-tmp/cache/libero-assets`；
- `hf-libero==0.1.4` asset path：将 `/root/.cache/libero/assets` 链接到持久化数据盘目录；
- 远程 LIBERO create/reset/close：在 `libero_10` task 0 的一个同步环境中通过；Observation keys 为 `pixels`、`robot_state`，action space 为 `(1, 7)`；
- 远程复现快照保存至 `/root/autodl-tmp/VLA-Intern-Sprint/results/training/`；
- 训练：尚未开始。

## 2026-08-11——迁移至 RTX 6000D、Runtime 验收与 Pi0.5 Sanity Run

### 从旧 RTX 4090 迁移

- 只迁移可复用数据，没有迁移旧 conda/Python 环境或 NVIDIA/CUDA 系统文件。
- Pi0.5 `model.safetensors`：14,467,165,872 bytes。
- 两台服务器的模型 SHA-256 一致：`21b8711787c4a75861b02cff6aa81675a3a943d32b435a68262ac4461e476ba4`。
- 以下全文件 manifest hash 也一致：
  - LIBERO dataset：`802b75450a4683be334457c9452117abb4fd66af1a9e098181c996a37b6e0c25`
  - LIBERO assets：`b8d3dd018ae7930f9930d075ed8a03c19303bc2a28f12e7a399c2af07d656b7d`
  - PaliGemma tokenizer cache：`2f92f05f705c8f33cdfa67358f289aa23c6de489b4cf5afd632aaab55aa49340`
  - 旧 results/logs：`27df2ead9b7650913c3e4150a9f3e4a693139243d3e66f16a6deb3f9f8d88bfd`
- 项目不再需要旧 RTX 4090，可以保持关机；没有删除其磁盘内容。

### 主要服务器硬件

- GPU：NVIDIA RTX 6000D；
- VRAM：`nvidia-smi` 报告 85,651 MiB，PyTorch 报告 83.05 GiB；
- Driver：`595.71.05`；`nvidia-smi` driver capability 为 CUDA `13.2`；
- CPU：Intel Xeon Platinum 8470Q，208 logical CPUs；
- RAM：1.0 TiB；
- 持久化磁盘：`/root/autodl-tmp`，150 GB。

### 重建 Runtime

- Python 3.12.13：`/root/autodl-tmp/miniforge3/envs/vla-intern`；
- PyTorch `2.8.0+cu128`；torchvision `0.23.0+cu128`；
- TorchCodec `0.7.0`；FFmpeg `7.1.1`；
- LeRobot `0.6.2`，commit `22bd7a2f489b367d8df42de803b1e8c4ca63a3f9`；
- Transformers `5.5.4`；Accelerate `1.14.0`；
- hf-libero `0.1.4`；NumPy `2.2.6`；
- `pip check` 无 broken requirements；
- RTX 6000D 上 CUDA 可用且支持 BF16。

### LIBERO 验收

- 最初的非交互 reset 因缺少 `~/.libero/config.yaml` 而阻塞，LIBERO 调用了 `input()` 询问自定义 dataset path。
- 按当前官方 `docker/Dockerfile.benchmark.libero` 格式重建配置，并根据新 conda 环境解析路径；没有修改上游源码。
- `libero_10` task 0 create/reset/close 通过。
- Observation keys：`pixels`、`robot_state`；action shape：`(1, 7)`。
- Robosuite private-macro warning 不影响运行。

### Pi0.5 离线 Preflight

- 迁移模型包含 812 个 safetensors entries。
- PaliGemma tokenizer：`GemmaTokenizer`，vocabulary size 257,153，从迁移 cache 离线加载。
- LIBERO dataset：273,465 frames、1,693 episodes。
- TorchCodec 成功解码两路 256×256 camera stream。
- State dimension 8，action dimension 7；采样 action 为有限值。

### 真实 20-Step Training Sanity

- 结果：通过，exit code 0；GPU 为 NVIDIA RTX 6000D；batch size 1。
- 精度：policy `bfloat16`、Accelerate mixed precision `bf16`。
- `gradient_checkpointing=true`、`train_expert_only=true`、`freeze_vision_encoder=true`。
- `compile_model=false`，关闭 EMA。
- 20 个 steps 均完成 forward、loss、backward 和 optimizer step。
- Peak allocated/reserved VRAM：12.8482/13.0039 GiB。
- 包含首个 data-load step 的 mean step time：0.4728 秒；steps 2–20 mean：0.2454 秒；median：0.2227 秒。
- 包含模型加载和 checkpoint 保存的 wrapper 总运行时间：131.95 秒。
- Initial/final loss：1.47037/1.91174；全部有限，无 NaN/Inf，无 OOM。
- Step 20 final checkpoint 保存成功，约 11 GB；运行后持久化磁盘可用 109 GB。
- 没有启动 Rollout、Evaluation 或长时间 fine-tuning。
- 本地结果索引：`results/training/pi05_sanity_new_server/`。
- 远程 checkpoint：`/root/autodl-tmp/VLA-Intern-Sprint/results/training/pi05_sanity_new_server/run/checkpoints/000020`。

## 2026-08-11——Pi0.5 第一次正式配对实验

### 源码确认的协议

- 重新读取 `AGENTS.md`、项目命令/日志、当前 `pyproject.toml`、`docs/source/pi05.mdx`、`docs/source/libero.mdx`、Pi0.5 config/model code、LIBERO environment config/wrapper 和 `lerobot_eval.py`。
- 未修改 LeRobot 上游源码。
- 固定 `libero_10` task 0、10 个正式 episodes、seeds 1000–1009、固定 initial states、hard reset、relative control、520-step limit、BF16 和 `n_action_steps=10`。
- 当前 `lerobot-eval` 只报告 success 和 aggregate wall time，不报告每次模型调用延迟或逐 episode length，因此新增项目侧 profiling wrapper。
- 正式 baseline 前先运行一个 seed 999、排除在对比外的 pipeline-smoke episode，并生成全部预期产物。

### Pretrained Baseline

- Checkpoint：`lerobot/pi05_libero_base` 的本地已验证 snapshot。
- 结果：0/10；每个 episode 都达到 520-step limit。
- Mean/p95 模型推理：181.6104/221.9903 ms。
- 正式评测 wall time：274.05 秒。
- Peak allocated/reserved VRAM：8.8700/9.1992 GiB；无 OOM。

### 第一阶段 Fine-Tuning

- 完成 2,000/2,000 optimizer steps，batch size 1。
- BF16 policy 与 BF16 mixed precision；expert-only；冻结 vision encoder；开启 gradient checkpointing；关闭 compile 和 EMA。
- Trainable/total parameters：693,422,112 / 4,143,404,816。
- Scheduler 自动将 warmup 从 1,000 缩放到 66，将 decay 从 30,000 缩放到 2,000。
- First/final profiled loss：1.470371/0.204011；所有记录 loss 有限。
- Mean/median step time：0.2237/0.2096 秒。
- 包含模型加载和两次 checkpoint 写入的 wrapper 总运行时间：578.46 秒。
- Peak allocated/reserved training VRAM：12.8482/13.0039 GiB；无 OOM，exit code 0。
- Checkpoint `001000` 和 `002000` 保存成功，每个含 optimizer state 约 11 GiB。
- 保存后持久化磁盘可用 87 GiB。

### 2k Checkpoint 配对评测

- 使用完全相同 baseline protocol 评测 `002000/pretrained_model`。
- 结果：10/10；episode length 227–370，mean 271.9。
- Mean/p95 模型推理：168.9912/208.3377 ms。
- 正式评测 wall time：153.32 秒。
- Peak allocated/reserved VRAM：8.8700/9.1992 GiB；无 OOM。

### 决策边界

- 在该配对任务上，十个 seed 全部从 baseline failure 变为 2k success：+100 个百分点，mean control steps 减少 248.1。
- Offline loss 与 closed-loop success 分开记录；不使用 loss 降低本身声称 Rollout 改善。
- 这只是一个 LIBERO-Long 任务，不是完整 LIBERO benchmark，也不声称总体 LIBERO success 为 100%。
- 在 2k 停止，保留 RTX 6000D 与 1k/2k checkpoint。没有下一步指令时不启动 5k、10k、更大 Rollout 或完整 Evaluation。
- 旧 RTX 4090 不再需要，可以保持关机。

## 2026-08-11——Checkpoint 稳定性与泛化前置评测

### 执行范围

- 保持正式 `libero_10` task-0 protocol 不变。
- Checkpoint 001000 在 seed label 1000–1009、固定初态 0–9 上评测 10 episodes。
- Checkpoint 002000 在一个不间断进程中用 seed label 1000–1029、固定初态 0–29 评测 30 episodes，避免新 20-episode 进程从 index 0 开始造成状态重复。
- 未进行训练、model/config/GPU 变更、上游源码修改、大量 Rollout 或完整 benchmark。

### 结果

- 1k：9/10（90.0%），mean/median length 290.0/273.0；fixed state 4 达到 horizon；mean/p95 inference 170.677/207.672 ms。
- 2k：28/30（93.33%），mean/median length 291.133/266.5；fixed state 14、18 达到 horizon；mean/p95 inference 168.289/206.702 ms。
- 两次运行 evaluation peak allocated/reserved VRAM 均为 8.870/9.199 GiB，无 OOM。
- 统一 2k run 的前十个 episode 精确复现早期 2k success flag 与 length。
- 匹配状态 0–9 上，1k 为 9/10，2k 为 10/10；state 4 从 1k 的 520-step failure 变为 2k 的 315-step success。

### Loss 解释

- Step-1000 point loss / trailing-100 mean：0.199160/0.279736。
- Step-2000 point loss / trailing-100 mean：0.204011/0.329684。
- 从 1k 到 2k loss 并非单调下降，但匹配 Rollout success 改善；不声称两者具有因果或单调关系。

### Initial-State 与 Seed 证据

- 当前 LeRobot 独立于 episode seed label 依次使用 `.pruned_init` row。
- 任务有 50 个存储 init-state row，按完整行 hash 均唯一；本次评测的前 30 行也唯一。
- 对相同固定 row 0 应用不同 seed 时，实测首个 observation 相同；连续固定 row 0 和 1 会同时改变 pixels 与 robot state。
- 因此这是一个任务上的 fixed-initial-state stability，不是 unseen-seed 或完整泛化结果。

### 失败审查与决策

- 1k 失败表现为反复接近/接触目标，但没有持续抓取与搬运。
- 两个 2k 失败均明显选择错误物体：一个将牛奶盒放入篮子，另一个碰撞杂物并放置非目标小盒。这些是外部可观察行为，grounding/recovery 原因仍是假设。
- 决策 B：保留 checkpoint 002000，在单纯增加 optimizer steps 前优先新增固定初态评测或真正不同任务测试。
- 生成报告后停止工作，未启动 5k/10k training。
- 报告：`results/evaluation/pi05_checkpoint_progression/`。

## 2026-08-11——Phase 1 Training Exposure Audit 与最终有效鲁棒性测试

### 训练暴露纠正

- 启动新 Rollout 前，审计实际训练命令、固定数据集元数据、起始 checkpoint config/README、当前 Pi0.5 文档和全部 LIBERO task definition。
- 2k run 使用完整 `lerobot/libero` revision `a1aaacb7f6cd6ee5fb43120f673cebb0cfea7dd4`：1,693 episodes、273,465 frames、40 tasks，无 task filter。
- 重点评测 `libero_10` task-0 指令是 dataset task index 5。
- 因此该 run 是 40-task continued fine-tuning，不是 task 0 的 task-specific fine-tuning；该数据集中不存在原计划的三个未参与 2k 训练任务。
- 起始 checkpoint 为 `lerobot/pi05_libero_base`；当前 LeRobot 文档说明它专门在 LIBERO 上训练，精确 per-episode/per-init-state pretraining exposure 不可得。
- 原计划 60 个 cross-task episodes 被跳过，而不是错误标为 unseen-to-fine-tuning transfer。

### 新增评测固定初态

- 源码和 runtime 检查确认 task 0 有 50 个 `.pruned_init` 状态。
- Profiling wrapper 新增项目侧 `--init-state-start` 支持；默认仍为 index 0，没有修改上游源码。
- 将同步环境从 init-state ID 30 开始，正好运行到 ID 49，共 20 episodes，seed label 1030–1049。
- 结果：18/20（90.0%），state 41 和 49 失败。
- Mean/median episode length：304.35/282.0。
- Mean/median/p95 inference：172.373/160.608/217.453 ms。
- Evaluation wall time：334.17 秒。
- Peak allocated/reserved VRAM：8.870/9.199 GiB；无 OOM。
- 全部 50 个存储固定状态上，checkpoint 002000 为 46/50（92.0%）。

### 失败证据与 Phase 1 结论

- State 41 明显将非目标小盒子放入篮子，未完成两个目标。
- State 49 在杂物碰撞后将牛奶盒干扰物放入篮子，未完成两个目标。
- 状态 0–49 中四个 2k 失败都涉及 wrong-object selection。这是观察到的案例模式，不是内部 VLM language-understanding error 的证明。
- 支持：匹配重点评测任务的改善，以及全部存储初态上的同任务鲁棒性。
- 不支持：held-out-task transfer/retention、catastrophic forgetting、positive transfer、完整 LIBERO success 或 open-world generalization。
- 推荐下一步 A：停止实验并整理 README/面试材料。LIBERO-plus 保持可选，未安装或运行。
- 报告：`results/evaluation/generalization/`。

## 2026-08-11——Phase 1 收尾

- 在 `notes/final_project_facts.md` 冻结具有安全声明边界的事实来源。
- 围绕已验证的 40-task continued fine-tuning、checkpoint progression、重点闭环评测、latency profiling、失败证据、局限性和贡献边界重写 README。
- 从保存的 CSV/JSON/JSONL 直接生成五张 README SVG；未编造数值，loss curve 未平滑。
- 索引现有代表性 Rollout 视频，没有将 MP4 重复复制到文档目录。
- 增加两版简历与 36 个面试问题，每题包含专业版、小白理解和面试口语版。
- SHA-256 和逐字节比较确认四个远程项目根目录意外副本与正式 `notes/` 或 `scripts/` 版本完全相同。只删除四个副本，保留正式文件和所有实验数据。
- 收尾期间未启动 training、Rollout、Evaluation、模型推理或 GPU compute；未启动 Phase 2。

## 2026-08-12——Phase 2 / Step 3：Observation → Pi0.5 → Action Chunk

- 读取并核对 Phase 1/Step 1/Step 2 文档、LeRobot `pyproject.toml`、Pi0.5 policy/config/processor、LIBERO env processor、现有 2k checkpoint 配置和 processor 统计；未修改 `lerobot/` 上游源码。
- 真实 2k checkpoint：`results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model`，8.8 GB；Pi0.5、BF16、chunk_size=50、7D action、train_expert_only=true、freeze_vision_encoder=true、gradient_checkpointing=true。
- Isaac/ROS 2 重新采集静止观测：两路 256×256 RGB、9D `/joint_states`、固定语言 `move the robot arm`；两张图与关节状态最大时间差 0.05 秒。
- State Adapter 从命名关节和 Isaac `/panda/panda_hand` 在 `/World` 下的真实变换出发；位置单位为米，Isaac `wxyz` 四元数显式重排为 LeRobot 要求的 `xyzw`，axis-angle 由官方 `LiberoProcessorStep` 计算。
- 真实 8D 样本：`[0.39052784, 0.00468519, 0.46012837, 2.88173223, 0.08130522, 1.21638811, 0.0, 0.0]`。该状态在结构上匹配，但 Isaac `/World` 与 LIBERO/robosuite 控制坐标域、gripper qpos 量程均未标定，因此语义兼容性为 PARTIAL。
- 两路图像通过 LeRobot `preprocess_observation` 和真实 `LiberoProcessorStep`，随后通过 checkpoint 自带 normalizer、Pi0.5 state prompt、tokenizer 和 device processor。外部相机映射 `observation.images.image`，手腕跟随视角映射 `image2`；后者不是已标定 eye-in-hand，因此图像语义为 PARTIAL。
- 首次 policy-only 尝试因单样本嵌套 quaternion 缺少 batch 维 `(4,)` 被官方 processor 拒绝；保留失败日志。修复只增加 batch 维到 `(1,4)`，没有伪造或改变状态。
- 同一真实静止观测最终真实调用 `predict_action_chunk` 3 次：407.157、186.766、186.218 ms；mean 260.047 ms、p95 385.118 ms。每次真实 shape `[1,50,7]`、float32、全部 finite、无 OOM。
- Torch peak allocated/reserved：8.870/9.201 GiB；推理后 `nvidia-smi` 进程占用快照 10,015 MiB。模型载入 99.004 秒。
- Action 经过 checkpoint 自带 unnormalizer 后只保存和审计，没有发布 ROS、没有执行。Pi0.5 7D 是 LIBERO OSC_POSE：前三维归一化 EEF position delta（默认缩放每维 ±0.05 m）、后三维归一化 EEF axis-angle delta（默认 ±0.5 rad）、第 7 维 gripper（-1 open，+1 closed）。Isaac Step 1 `/joint_command` 是 7 个关节绝对位置，二者 MISMATCH。
- 最后写 `environment.txt` 时因远程项目根目录不是 Git repository 返回 128；发生在 action/latency/memory 全部保存后，没有重复运行模型。该非核心错误已在本地脚本修复为可选 Git 字段并如实记录。
- 最终确认无 Isaac/Pi0.5 计算进程，GPU 0 MiB；未开始 Step 4、Rollout、Evaluation、抓取、IK、MoveIt 或任何 VLA 动作执行。
## 2026-08-12——Phase 2 / Step 4：Action Adapter 与单动作执行

- 从实际 checkpoint postprocessor、LIBERO dataset metadata、robosuite 1.4.0 `osc_pose.json`、`scale_action()`、`set_goal_orientation()` 和 Panda gripper 源码确认动作语义。
- 选择 Isaac Sim 6.0.1 当前官方 PINK API；没有使用 deprecated Lula、MoveIt 或自写 Jacobian/IK。
- 合成测试先后暴露 PINK extension 未启用、Warp input 类型和 joint-limit API 结构问题；这些失败都发生在首个合成 command 发送前。修复后合成 frame/gripper test 全部 PASS。
- 真实 Step 4：一次 Pi0.5 inference、一个首动作、Franka 可测运动；剩余49步未执行、没有自动第二次 inference、没有闭环。
- 实测：inference 577.160 ms；adapter 0.407 ms；PINK mean/p95 1.950/2.356 ms；command→movement 97.120 ms；目标位置/姿态误差 1.115 mm/7.030 mrad；OOM=false。
- 系统 `ffmpeg` 不在 PATH，未安装新软件；改用现有 `vla-intern` 环境中的 FFmpeg，将90帧真实画面封装为9秒 MP4。
- 完成后停止 Isaac、Pi0.5 与测试进程，停在 Step 4。

## 2026-08-12——Phase 2 / Step 5：Closed-loop VLA Runtime Smoke Test

- 采用严格 `MAX_CYCLES=5` 的 receding-horizon：每轮保存新 external/wrist RGB、8D state、语言和时间戳，真实调用一次 2k Pi0.5 `predict_action_chunk`，只执行索引 0；其余 49 步均未执行。
- 五轮 external/wrist 图像 SHA-256 均各自唯一；四组相邻 robot state 均改变；五个首动作均不同。这证明是五次 Observation → Inference → Action → Robot 反馈，而不是一次推理后连续执行五个缓存动作。
- 五次推理延迟：421.738、186.916、187.060、187.041、185.954 ms；mean/median/p95 为 233.742/187.041/374.803 ms；去掉 Cycle 0 warm-up 后 mean 为 186.743 ms。
- Action Adapter mean/p95 为 0.265/0.366 ms；PINK 五轮等长度控制的 mean 为 1.876 ms，保存的逐轮 p95 最大值为 2.245 ms；Observation 到 motion complete mean 为 2234.200 ms。
- EEF 从 `[0.389247, 0.004672, 0.456240]` m 移至 `[0.389257, 0.023057, 0.438739]` m，起终点直线位移 25.384 mm；累计关节端点位移 0.288697 rad。
- Torch peak allocated/reserved 为 8.868/9.199 GiB；`nvidia-smi` timeseries peak used 为 13,292 MiB；无 OOM。
- 成功运行中 Safety rejection、timeout、workspace violation 和 joint violation 均为 0；最大图像/状态时间差 2.110 ms。
- Attempt 001 因 PINK `position_cost` 错传整数，在 Cycle 0 观测与动作前触发 `TypeError`；执行动作数为 0。修正为 `5.0` 后再运行，原始失败证据保存在 `attempt_001_before_cycle0/`。
- 生成 150 帧、14.8 秒 MP4 与真实起终点 PNG。完成后 Isaac、Pi0.5 和 wrapper 进程均停止，GPU 无 compute process；LeRobot upstream clean。
- 当前结论仅为 closed-loop runtime PASS。没有目标物体、任务成功判据、抓取或成功率评测，不声称 LIBERO transfer、zero-shot manipulation 或跨域泛化。

## 2026-08-12——Phase 3 / Step 6：LIBERO → Isaac Cross-Simulator Task Validation

- 从实际 `hf-libero 0.1.4` / `robosuite 1.4.0` 源码和 runtime 审计 `libero_10` task 0；确认 BDDL、固定 state 0/1/2、OnTheGroundPanda、桌面、两路相机与真实 `In` success predicate。
- 复用现有 alphabet soup、tomato sauce、basket、living-room table mesh/texture，以 Isaac 6.0.1 转换 USD；源文件和 USD 都记录 SHA-256。桌子 bump map 在源目录缺失，警告保留。
- 动态场景闸门 PASS；success detector positive/negative synthetic test 均 PASS；正式 rollout 前保存 LIBERO/Isaac external+wrist 对照图。
- 使用冻结的 `002000/pretrained_model`，语言保持 focus instruction；无训练、LoRA、Full Fine-Tuning 或权重更新。
- 三个 episode 分别 hard reset 到 fixed initial state 0/1/2；每回合 MAX_CYCLES=100，receding horizon K=1，每轮一次真实 `predict_action_chunk`，只执行 `action_chunk[0]`。
- 三回合均完成 100 cycles 并 `HORIZON_REACHED`，success=0/3，无安全停止、controller failure、人工干预或 OOM。总计 300 次真实 Pi0.5 inference。
- 推理 mean/median/p95：182.876/181.603/184.141 ms；每回合跳过前 10 次后 steady-state mean 181.916 ms。Adapter mean/p95 0.229/0.251 ms；PINK cycle mean/p95 1.982/2.125 ms。
- Torch peak allocated/reserved：9,522,268,160 / 9,877,585,920 bytes；`nvidia-smi` 全局 peak 13,059 MiB。
- Observed：机械臂会向任务区与篮子附近运动，但三个 episode 的两个目标罐测得位移均为 0，没有有效抓取、搬运或放置。分类：failed approach、failed grasp、horizon reached。
- Experimental Pipeline=PASS，Policy Task Result=0/3，Task Transfer=FAIL。不得称 unseen-task、zero-shot new-task、open-world 或 sim-to-real。
- 完成后确认无 Isaac/Pi0.5/ROS2 实验进程，GPU 0 MiB/0%；停在 Step 6，不自动进入 Step 7。
## 2026-08-13：Phase 3 / Step 7A 动作一致性审计

- 在 RTX 5090 远程服务器完成 LIBERO → Isaac Action Parity Audit；没有调用 Pi0.5，没有训练，没有任务 rollout，也没有重跑 Step 6。
- 重新核验远程 `hf-libero 0.1.4` / `robosuite 1.4.0` 源码：OSC_POSE 平移缩放为 ±0.05 m，旋转缩放为 ±0.5 rad，姿态组合为 `R_delta @ R_current`，Panda gripper 为 `-1=open`、`+1=closed`。
- 14 个 canonical action 均独立 reset。LIBERO 端每个动作执行一个 20 Hz 控制步；Isaac 端通过现有 Action Adapter → Safety → PINK → Franka 链路执行 3 个 60 Hz 物理步。
- 结果保存于远程和本地 `results/phase3_step7/action_parity/`。夹爪 open/close 为 MATCH；平移 2 个 APPROXIMATE、4 个 MISMATCH；旋转 3 个 APPROXIMATE、3 个 MISMATCH；总体按实际单步轨迹为 MISMATCH。
- 所有 Isaac 案例通过 Safety、PINK、关节限位和 finite 检查，无 OOM。该结果只能说明单步跨模拟器跟踪仍不一致，不能直接归因于 Pi0.5/VLM，也不能单独解释 Step 6 的 0/3。
- Step 7A 结论：PARTIAL。下一步若获授权，应先做 State Mapping / EEF Calibration Audit；本轮完成后停止。
## 2026-08-13：Phase 3 / Step 7A.1 Action Parity Mismatch Localization

- 新 RTX 5090 实例快速检查通过：GPU `NVIDIA GeForce RTX 5090`，驱动 `580.105.08`，显存 `32607 MiB`，当前占用 `0 MiB`；`/root/autodl-tmp/vla_env.sh`、项目目录和历史 Step 7A 结果均存在。
- 发现迁移后的 `results/phase3_step7/action_parity/` 是早期不完整副本；完整 14-action 历史证据位于 `action_parity_attempt2/`，本次未把残缺目录当作输入。
- 仅离线读取完整 Step 7A JSON。平移 target 方向余弦 `0.999974`～`0.999990`，目标幅值比 `0.994`～`1.006`；旋转 target 轴/符号余弦约 `0.999990`～`1.000000`，目标幅值约 `0.025 rad`。未发现 scaling/sign/rotation-order 的明确错误。
- EEF 参考点：LIBERO 为 `robot0_eef_pos`/`ee_ori_mat`，Isaac 为 `panda_hand` 加 `95.1035 mm` position offset、姿态直接取 `panda_hand`。state 0 位置差约 `0.431 mm`，初始姿态相差约 `1.571 rad`，确认旋转参考系未统一。
- 分类：平移 MISMATCH 记为 `TRACKING_MAGNITUDE_MISMATCH`；旋转 MISMATCH 记为 `REFERENCE_POINT_MISMATCH`（次级 tracking mismatch）。没有确认 Action Adapter bug、scaling bug 或 rotation composition bug。
- Step 7A.1 结论：不修复、不重跑 Step 7A；下一步选择 B：State Mapping / EEF Calibration Audit。当前停止。
## 2026-08-13 — Phase 3 / Step 7B State Mapping / EEF Calibration Audit

- 在 RTX 5090 上完成五姿态静态采样：同一组明确 Panda 7D arm joint vector 分别写入 LIBERO 和 Isaac；没有调用 Pi0.5、训练、task rollout 或 Step 6 重跑，也没有修改 State Adapter 或 LeRobot 上游源码。
- Pi0.5 实际状态链已按源码确认：`robot0_eef_pos`、`robot0_eef_quat (xyzw)`、`robot0_gripper_qpos` 经 `LiberoProcessorStep` 形成 `[position(3), axis-angle(3), gripper_qpos(2)]`。`controller.ee_ori_mat` 不是当前 policy state 的姿态源，只用于控制器 frame 诊断。
- 当前 Isaac State Adapter 使用 `panda_hand` 的 world pose、`tool_position = hand_position + R_hand @ [0,0,0.0951034858]`、以及两个 finger qpos。五姿态公式残差为数值零，未确认 world-fixed tool offset bug。
- 五姿态中，Isaac tool point 到 LIBERO `robot0_eef_pos` 直接误差为平均 `37.870 mm`、最大 `70.814 mm`、最小 `2.517 mm`。纯诊断刚体配准后仍为平均 `37.142 mm`、最大 `63.719 mm`，不能作为可直接应用的固定外参修复。
- policy-source `robot0_eef_quat` 与 Isaac `panda_hand` 的姿态误差为平均 `0.434 rad`、最大 `0.862 rad`、最小 `0.025 rad`；单一固定旋转没有显著改善，结论为 APPROXIMATE。约 `1.571 rad` 的 controller matrix 差异属于独立控制器 frame 约定，不应被误写成 Pi0.5 state 输入的固定 90 度 bug。
- LIBERO gripper 的 open/intermediate/closed 为 `[0.04,-0.04]` / `[0.02,-0.02]` / `[0,0]`，Isaac 为约 `[0.04,0.04]` / `[0.02,0.02]` / `[0,0]`。开合趋势一致，但数值符号不等价；当前 State Adapter 直接传值，因此 gripper numeric mapping 为 MISMATCH。
- image-to-joint 最大 skew 采用既有 RTX 5090 migration smoke 记录 `0.15 s`，本阶段独立分类为 POTENTIAL ISSUE，未修改同步策略。
- 最终分类：Position=MISMATCH；Orientation=APPROXIMATE；Tool-point=APPROXIMATE；Gripper=MISMATCH；Timestamp=POTENTIAL ISSUE；Overall State Mapping=MISMATCH。该状态映射问题可能参与解释 Step 6 的 0/3，但本审计不能证明它是唯一原因，也不能归因到 Pi0.5/VLM/attention 内部。
- 正式 BEFORE-FIX 证据：`results/phase3_step7/state_mapping_audit/`。前三版分析分别作为 `state_mapping_audit_attempt1_controller_matrix_invalid/`、`state_mapping_audit_attempt2_policy_quaternion_draft/`、`state_mapping_audit_attempt3_text_correction/` 保留，不删除、不作为最终结论输入。
- 当前不实施修复。唯一推荐后续方向：A. Fix State Mapping and rerun calibration；需用户明确授权后再做。
## 2026-08-13 - Phase 3 / Step 7B.1 状态映射修复与静态复核

- 严格保留 `results/phase3_step7/state_mapping_audit/` 的 Step 7B before-fix 证据，并在独立 `state_mapping_fix/` 目录保存本轮产物。
- 位置候选改为资产中的真实 USD 子 prim `/World/Robot/panda_hand/tool_center`。原五姿态的 mean/max 从 `37.870/70.814 mm` 降至 `7.874/8.207 mm`；五个不参与选择的 hold-out 姿态从 `62.852/79.705 mm` 降至 `7.800/7.898 mm`。仍有约 8 mm 残差，位置为 `APPROXIMATE`。
- 没有加入固定姿态补偿；姿态 comparison 仍无法得到受 frame semantics 证明的 rigid transform，保留 `UNRESOLVED`。
- 全量固定 revision 数据集审计（273,465 帧）显示两维夹爪 state 几乎总为相反符号（`0.99876767`）。项目 State Adapter 将 Isaac `[finger1, finger2]` 改为 LIBERO-compatible `[finger1, -finger2]`；open/intermediate/closed CPU 单元测试在远程通过，夹爪为 `MATCH`。
- 最小代码修改仅为 `phase3/scripts/state_mapping_adapter.py` 与 `phase2/scripts/policy_input_adapter.py`。没有改上游 LeRobot、Action Adapter、PINK、安全逻辑、Camera、Pi0.5、Controller、Scene、Task 或冻结 Step 6 脚本。
- 本轮只做静态 capture 既有结果的离线 JSON 复核：未调用 Pi0.5，未启动 task rollout，未训练，未重跑 Step 6，未修改 timestamp 策略。最终 10 个 JSON 均可解析；RTX 5090 为 `0 MiB / 0%`，无残留 GPU compute process。
- Overall State Mapping 从 `MISMATCH` 提升为 `APPROXIMATE`。旧映射可能影响 Step 6 的 0/3，但不能证明是唯一因果；此时不应重跑 Step 6。下一诊断建议为 Scripted Grasp Oracle，需另行明确授权。
## 2026-08-13 - Phase 3 / Step 7C Scripted Grasp Oracle

- 目标：在完全不使用 Pi0.5、视觉识别和语言决策的情况下，验证 Step 6 Isaac/Franka/PINK/夹爪/PhysX 是否具备机器人侧抓取能力。
- 复用 Step 6 initial state 0、Franka、桌面、两个目标物体、basket、碰撞和物理设置；对象目标位置和 bounding dimensions 由 live Isaac 场景读取，top-down 位姿按真实碰撞盒几何计算。
- 先执行一次 `DIAGNOSTIC / NOT COUNTED`。第一次诊断发现 close target 被 PINK 全 DOF 目标覆盖，实际宽度保持约 71 mm；修正为每个 arm command 后持续重申 finger target，第二次因本地命令时限中断且安全终止残留 Isaac 进程，第三次独立诊断通过：alphabet soup 最大竖直位移 `146.264 mm`，最终保持 `145.774 mm`。
- 正式协议固定六次且每次 hard reset：alphabet A0/A1/A2 全部 `SUCCESS`；tomato T0/T1/T2 全部在 descent 阶段 `SAFETY_STOP`。正式统计为 alphabet `3/3`、tomato `0/3`、总体 `3/6`。
- alphabet 成功 trial 的物体真实运动证据：初始 z `0.478715 m`，最大 lift z 约 `0.624979 m`，最终 z 约 `0.624489 m`；最大竖直位移 `0.146264 m`，最终保持 `0.145774 m`，超过 `0.060 m` 阈值。
- 夹爪判据不要求宽度归零：close target=0 持续下发且接触后稳定；alphabet 夹爪宽度约 `0.07118 m`，物体被夹持抬升，因此仍是成功。没有把 gripper closed 单独当成功。
- Tomato 三次没有形成完整 object motion evidence，因为在 descent 阶段触发 safety stop；原始 `exception.txt`、`result.json` 和 launch log 均保留。没有继续重试，没有调摩擦、质量、碰撞体、夹爪力或 solver。
- Step 7C 判定：`PARTIAL`，不是 `ROBUST PASS`。Robot-side pipeline 对 alphabet soup 已验证；对 tomato sauce 尚未验证。旧 Step 6 `0/3` 不能归因于 Pi0.5，也不能声称 gripper/physics 已完全排除。
- Oracle 不使用相机或 observation，因此 Step 7B 的 `0.15 s` image-to-joint skew 与本轮失败无关。最终 GPU 空闲：RTX 5090 `0 MiB / 0%`。
- 证据目录：`results/phase3_step7/grasp_oracle/`；说明：`notes/phase3_step7_grasp_oracle.md`；学习笔记已补充 `notes/phase3_step7_learning.md`；六个 MP4 已保存在 `assets/videos/`。

## 2026-08-13 - Phase 3 / Step 7C.1 Tomato Safety-Stop 静态定位

- 只读取冻结的 Step 7C 结果、成功 alphabet 轨迹、Step 6 dynamic scene export 和 Oracle 源码；没有启动远程 Isaac/GPU，没有调用 Pi0.5、训练、rollout 或新增正式 trial。
- Tomato 三个目录均有 23 张帧：start 1、open 1、approach 21、descent 0；异常均来自 `execute_stage("descent", ...)` 的 `RuntimeError("SAFETY_STOP")`，且三个异常文件 SHA-256 相同。
- 结合代码控制流确认：安全检查若在 descent step 0 通过，会立即保存第一张 descent 帧。因此三次均定位为 `DESCENT_STEP_0_SAFETY_GATE_REJECTION`。
- 当前安全 `if` 合并了 non-finite、最大 joint delta 超过 `0.05 rad`、低于 lower limit、高于 upper limit 四类条件；失败路径没有写出 safety/trajectory/controller/eef，因此精确 leaf 仍为 `UNRESOLVED_FROM_EXISTING_LOGS`。
- PINK reset 与 forward 没有进入显式 `IK_FAILURE` 分支；准确结论是 PINK 返回目标后被安全层拒绝，不能据此宣称 PINK 求解器本身失败。
- Step 7C Oracle 没有 Cartesian workspace min/max 检查，不能套用 Step 6 workspace 常量。Tomato 既有 geometry 数据有限，目标高度尺度与成功 alphabet 接近，未发现明显无效 target，但失败 trial 的精确 live target 未保存，几何不能完全排除。
- Tomato 未进入 close/lift，故不能评价或归因于 contact、gripper、friction、mass、collision、lift 或 drop；也与未使用的 Pi0.5、视觉和 timestamp skew 无关。
- 最小后续建议只是在抛异常前记录独立安全 leaf 和完整 joint/limit/EEF payload；未执行该修改、未放宽阈值。若以后获授权，只需一次 `DIAGNOSTIC / NOT COUNTED` tomato trial。当前 Pi0.5 diagnostic rollout=`NO`。
- 独立证据目录：`results/phase3_step7/tomato_safety_localization/`；说明：`notes/phase3_step7_tomato_safety_localization.md`。

## 2026-08-13 - Phase 3 / Step 7C.2 Tomato Safety Telemetry Diagnostic

- 获明确授权后仅运行 1 次 `DIAGNOSTIC / NOT COUNTED` tomato trial；新增独立 telemetry 脚本和运行入口，没有修改冻结的 Step 7C Oracle。
- 复用 state 0、tomato live geometry、原 pre-grasp/descent target、PINK + OSQP、240 步 approach、原 descent setpoint、physics timestep、gripper target 和 `MAX_JOINT_STEP_RAD=0.05`。
- Diagnostic 完成 pre-grasp，并在 `descent step 0` 精确复现 Safety Stop；PINK status=`TARGET_RETURNED`，joint actual/target 全部 finite。
- 最大绝对 joint delta 为 `panda_joint6` 的 `0.04410219192504883 rad`，小于 `0.05 rad`，九个 joint 均无 delta violation；所有 joint 均无 lower-limit violation。
- 唯一 violation 为 `panda_finger_joint2`：target=`0.04000000283122063 rad`，upper=`0.03999999910593033 rad`，仅超出 `3.725290298461914e-09 rad`。精确 reason code=`JOINT_UPPER_LIMIT`。
- 已确认根因：PINK 全 DOF finger target 与 Isaac runtime finger upper limit 的 float 边界差异，被当前无容差严格 `target > upper` Safety 比较拒绝。不是 non-finite、joint-delta、physics、gripper mechanical capability、Pi0.5、视觉或 timestamp 问题。
- Runtime=`34.616132 s`，diagnostic exit=`0`；完整 PINK/joint/limit/EEF telemetry 已保存。正式 Step 7C 汇总与三个 tomato result 哈希运行前后一致，统计仍为 alphabet `3/3`、tomato `0/3`、overall `3/6`。
- 本轮没有修复。未来最小建议是统一比较精度，仅对 float epsilon 内越界夹回精确 limit，真实越界仍拒绝，并保持 `0.05 rad` 阈值不变。
- 若获后续授权，建议在独立 post-fix 目录运行 3 次相同协议 tomato Oracle；不得覆盖原 `0/3`。当前 Pi0.5 diagnostic rollout=`NO`。
- Step 7C.2=`PASS`，仅表示精确 Safety trigger 定位成功。

## 2026-08-13 - Phase 3 / Step 7C.3 Floating-Point-Safe Safety Fix

- 仅修复 Step 7C.2 已确认的无容差 joint-limit 比较；没有修改真实 joint limit、PINK、轨迹、physics、success metric 或 `MAX_JOINT_STEP_RAD=0.05`。
- runtime target、joint limit 与 comparison dtype 均为 `float32`；采用每个 limit 的 `2 ULP`，finger 上限附近为 `7.450580596923828e-09 m`。容差内只 clamp 回原 limit，真实超限仍拒绝。Step 7C.4 源码审计确认 finger 为 prismatic joint，因此这里的历史 `rad` 标签应纠正为 `m`。
- Isaac 启动前的正式纯数值测试 `13/13 PASS`，覆盖 upper/lower 边界、一个 ULP、真实超限、NaN/±Inf 与 joint delta。第一次测试辅助逻辑失败记录保留，没有启动 Isaac。
- 严格只运行三次 Tomato post-fix hard-reset trial，没有第 4 次且没有重跑 Alphabet。原 Step 7C 结果哈希保持不变。
- 三次 descent step 0 均通过项目 Safety，确认原 false-positive `JOINT_UPPER_LIMIT` 已消失；各保存一个 `FLOAT_TOLERANCE_UPPER_CLAMP`。
- 三次均继续到 descent 中段后出现新的 `IK_FAILURE`：PINK 内部报告 Joint 8 current configuration `0.04000149667263031` 超过其 `0.04` 上限，随后 `controller.forward` 返回 `None`。
- 每次最后保存的 descent 样本为 step 72；精确失败只能界定在 step 73～84。异常路径未保存完整 telemetry，因此确认 clamp 至少 3 个，不能声称全过程精确总数为 3。
- Tomato AFTER=`0/3`，完整 descent=`0/3`，grasp stage=`0/3`，lift=`0/3`。结合冻结 Alphabet `3/3`，Robot-side Oracle 仍为 `PARTIAL`，Step 7C.3=`PARTIAL`。
- 按约束没有自动修复第二个问题，没有运行 Pi0.5、Step 6、训练、LoRA 或 RL；RTX 5090 最终为 `0 MiB / 0%`。

## 2026-08-13 - Phase 3 / Step 7C.4 PINK Finger-Joint Configuration Limit Static Audit

- 只读取项目代码、既有 telemetry、RTX 5090 上实际安装的 Isaac Sim PINK extension 0.1.3、PINK prebundle、Franka URDF 和 Articulation API；没有启动 Isaac 或任何新实验。
- 完整 joint order 确认为 0～6 arm、7 finger1、8 finger2；Isaac 场景有显式顺序断言，PINK loader 按相同 URDF 顺序收集全部 `nq>0` joint。没有 joint-ordering bug。
- 两根 finger 是独立 prismatic joint，单位为米；bundled URDF 已移除 mimic。PINK configuration、configuration limits、9D velocity、PostureTask 和 output 都包含 fingers。
- `panda_hand` FrameTask 不直接依赖下游 fingers，但完整 9D PostureTask 会产生 finger velocity。项目随后用独立 gripper command 覆盖 PINK finger target，因此 merge ordering 正确，configuration/QP 层仍未解耦。
- 失败调用中 `robot.get_dof_positions()` 的 finger2 current q 已是 `0.04000149667263031 m`；映射为 float64 PINK q[8] 后，`_solve_ik()` 在构建 QP 前调用 `Configuration.check_limits(tol=1e-6)` 并拒绝。该调用没有生成 velocity、integrated q 或 target。
- current excess 为 `1.49667263030923e-6 m`，约为项目 2-ULP tolerance 的 `200.88` 倍；不得扩大项目 Safety tolerance。
- 已确认直接根因：独立 gripper 被包含在 arm IK live configuration，使已轻微超限的 Isaac finger current state 阻断整个 arm IK。实际 drive 为什么达到该超限值仍未记录完整；position-control tracking overshoot 为 `POSSIBLE`。
- 工程 ROI：建议 `MINIMAL_FIX_AND_ONE_DIAGNOSTIC_TRIAL`，但本阶段未执行。未来可将 PinkRobot controlled joints 限定为 7 个 arm joints，gripper 继续独立控制；若需要 upstream fork/reduced-model redesign，则停止 Franka deep dive。
- Step 7C.4=`PASS` 仅表示静态定位完成；Pi0.5 diagnostic rollout=`NO`。RTX 5090 保持 `0 MiB / 0%`。
## 2026-08-13 - Phase 3 / Step 7C.5 Arm / Gripper IK Decoupling

- 根据 Step 7C.4 已确认根因，只实施一个架构修复：PINK 从 9D arm+finger 改为真正的 7D arm-only configuration；gripper 保持独立 Isaac command 与独立 Safety 路径。
- 未修改 upstream PINK、joint limits、PINK tolerance、项目 Safety threshold、physics、friction、mass、collision、drive、trajectory、controller cost、grasp target 或 success metric。
- Pinocchio `buildReducedModel()` 因 bundled URDF 重复 frame 名拒绝构造；改为从实际 bundled Franka URDF 生成项目侧 arm-only URDF，仅移除两个 finger joint 及其下游 fingertip 子树。原 URDF 未修改，`panda_hand` 保留。
- Isaac 启动前 A–H 全部通过：`nq=nv=7`、controlled joints 精确为 7 个 arm joints、finger1/2 不在 PINK、arm mapping 0~6 正确、gripper target 独立、最终 articulation mapping 无错位，Safety regression `13/13 PASS`。
- 严格只运行 1 次 Tomato `DIAGNOSTIC / NOT COUNTED`：exit code 0，runtime `22.8412 s`，无 exception、无 OOM。
- Runtime PINK 始终观测为 7D；完整通过 descent step 0~199 和原失败区间 73~74，原 `Joint 8 violates configuration limits` 未再次出现。
- pre-grasp、完整 descent、gripper close、lift 与 hold 均完成。Tomato 最大竖直位移 `146.5309 mm`、最终竖直位移 `145.8925 mm`，高于固定 `60 mm` lift threshold。
- 没有专用 contact sensor，因此只记录物体运动证据，不声称直接测得 contact。
- 历史 Step 7C 正式结果未修改且哈希复核一致：Alphabet `3/3`、Tomato `0/3`、Overall `3/6`。本次成功不计入正式统计。
- Pi0.5、`predict_action_chunk`、训练、LoRA、RL、Step 6 和正式 Tomato trial 均未运行；结束后 RTX 5090 为 `0 MiB / 0%`。
- `Step 7C.5 = PASS` 只表示本地 arm/gripper 架构 bug 已修复并通过一次诊断；不证明 formal Tomato Oracle 稳健，不代表 Pi0.5、LIBERO transfer、跨域泛化或真实机器人部署。
## 2026-08-13 - Phase 3 / Step 7C.6 Tomato Fixed-Protocol Post-Decoupling Validation

- 在 Step 7C.5 代码状态上，不再修改 Oracle、7D PINK、gripper、Safety、tolerance、joint limit、physics、object/grasp pose、trajectory、success metric 或 controller cost。
- 运行前冻结 Oracle、Safety helper、scene、common config、arm-only helper/URDF 和已安装 PINK controller SHA-256；三次 trial 后复核，diff 为 0 字节。
- Safety regression 继续为 `13/13 PASS`。
- 严格只运行 Tomato validation 00/01/02 三次正式 hard-reset trial，没有第 4 次、失败重跑、seed 筛选或 Alphabet/Step 6 重跑。
- 三次均为 SUCCESS：pre-grasp 完成、descent 200/200、gripper close 执行、object motion observed、lift/hold 成功。
- 三次 runtime PINK 均为 `nq=nv=7`，finger 不在 configuration；PINK solve failure=0、finger configuration-limit failure=0、Safety violation=0。
- 三次最大/最终竖直位移均为 `146.5309/145.8925 mm`，固定 lift threshold 为 `60 mm`；最终 finger1/finger2 约为 `0.035155/0.035180 m`。
- 没有 contact sensor，因此只记录 object motion / grasp-lift behavior observed，不声称 direct contact measured。
- 三段各自 66 帧、15 FPS 的未经剪辑正式视频已生成并保存哈希。
- 运行器通过 SSH 时最初把三个 `exit_code.txt` 写成 `0n`；在确认顶层命令退出 0、三个完整 `result.json` 均为 SUCCESS 后，只将这三个元数据文件规范化为 `0`，未修改任何仿真证据或结论。
- 历史结果保持：Alphabet Step 7C=`3/3`，original Tomato Step 7C=`0/3`，Step 7C.3 Tomato=`0/3`，Step 7C.5 diagnostic success=`NOT COUNTED`。
- Step 7C.6 formal after：Tomato=`3/3`，Tomato post-decoupling=`ROBUST PASS`；basic robot-side scripted Oracle pipeline 当前结论=`ROBUST PASS`。
- 本实验未调用 Pi0.5/`predict_action_chunk`，不能证明 Step 6 Pi0.5 `0/3` 由 robot-side bugs 导致。推荐但未执行的下一步为 `ONE_POST_STATE_MAPPING_PI05_DIAGNOSTIC_ROLLOUT`。
## 2026-08-13 - Phase 3 / Step 7D ONE Post-Fix Pi0.5 Diagnostic Rollout

- 严格只运行 1 次 `DIAGNOSTIC / NOT COUNTED` episode：Step 6 fixed initial state 0、最多 100 cycles、K=1、每 cycle 一次真实 Pi0.5 inference 且只执行 `action_chunk[0]`。没有 state 1/2、补跑、seed 筛选、训练、LoRA 或 RL。
- 使用原 Step 6 的 `002000/pretrained_model`；`model.safetensors` SHA-256 为 `590c83ba6061fbfeb887d675deb9b173bbe23f65722c6b38ce242825ffbac631`，权重未改变。
- 复用原 Step 6 scene/task/object/camera/instruction/state0/success detector；启用已确认的 native `tool_center` Position Mapping、`[finger1,-finger2]` Gripper Mapping、7D arm-only PINK、独立夹爪和 floating-point-safe Safety。没有新增 orientation 或 timestamp fix。
- AFTER 完成 100/100 cycles，结果为 `HORIZON_REACHED`，任务未成功；alphabet 和 tomato 最大/最终位移均为 0，未形成 plausible grasp attempt。最小 tool-center 距离为 alphabet `0.263074 m`、tomato `0.201323 m`，均未优于 Step 6 BEFORE。
- 行为分类为 `NO_CLEAR_IMPROVEMENT`；失败标签为 `FAILED_APPROACH / FAILED_GRASP / HORIZON_REACHED`。这不证明 Pi0.5 内部语义、VLM、attention、orientation、timestamp 或 domain gap 的单一根因。
- 运行层无关键回归：Safety violation=0、PINK failure=0、finger configuration-limit regression=0、OOM=false；说明已确认的 robot-side blocker 被清除，但不能把 Step 6 原 0/3 仅归因于这些 bug。
- Pi0.5 latency：mean `259.769 ms`、median `237.058 ms`、p95 `322.760 ms`。Torch peak allocated/reserved 为 `9,522,268,160 / 9,877,585,920 bytes`；nvidia-smi peak `12955 MiB`；最终 RTX 5090 为 `0 MiB / 0%`。
- 最后一轮策略完成文件存在亚秒级握手竞态：100 次 inference 和 100 个 cycle 均完整，Isaac exit=0，但策略在顶层 completion 原子落盘前结束检查，原始 policy exit=1。未重跑；保留原始文件并新增 `policy_handshake_reconciliation.json`，未来脚本只增加 5 秒有界等待。
- Step 7D=`PASS` 仅表示单次授权诊断完整执行与证据归档；Diagnostic task=`FAILURE`。推荐 `FREEZE_FRANKA_ISAAC_MAINLINE`，不再增加 Franka benchmark episode，不自动训练/LoRA/RL。
- 产物：`results/phase3_step7/pi05_postfix_diagnostic/`、`notes/phase3_step7_pi05_postfix_diagnostic.md`、`assets/videos/phase3_step7_pi05_postfix_diagnostic_state0.mp4`。视频 SHA-256 为 `f50ee2a688ac13fdc9727504914ec31a5b228c636dd428fa8ed3bbd628a64197`。
