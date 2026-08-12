# 每日记录

## 2026-08-12 — Phase 2 / Step 1 完成

- 冻结 Phase 1 结果，未启动 Pi0.5、LIBERO、训练、Rollout 或 Evaluation。
- 根据 NVIDIA 当前官方文档选择 Isaac Sim 6.0.1；服务器为 Ubuntu 22.04.5、Driver 595.71.05、RTX 6000D 85,651 MiB、1 TiB RAM。
- 在 `/root/autodl-tmp/isaac_sim/venv` 创建独立 Python 3.12 环境；使用数据盘缓存，最终数据盘约 63 GiB 可用。
- 安装 ROS 2 Humble ros-base 并通过 `ros2 doctor --report`；构建 `vla_manipulator_runtime`。
- 默认 Isaac base experience 的拆包依赖需要额外官方 asset/cortex/replicator/test/example 包；未修改 NVIDIA upstream。
- 修正 Isaac 内置 Humble `LD_LIBRARY_PATH` 后，ROS 2 Bridge 成功加载内部 rclpy。
- Isaac Sim 6.0.1 headless + RaytracedLighting 启动成功；官方 Franka 6.0 USD 加载到 `/panda`，physics 正常运行。
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
