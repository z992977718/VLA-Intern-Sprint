# RTX 5090 克隆迁移审计（2026-08-13）

## 范围与边界

本记录只验证 RTX 6000D 克隆到 RTX 5090 后的环境、已有实验资产和一次最小推理链路。没有重新训练、没有运行完整 rollout/evaluation、没有执行任何环境 action，也没有覆盖历史结果。

远程持久化项目根目录：`/root/autodl-tmp/VLA-Intern-Sprint`。

## 环境结论

- GPU：NVIDIA GeForce RTX 5090。
- Driver：580.105.08；`nvidia-smi` 报告 CUDA 13.0。
- 总显存：32,607 MiB（33,668,988,928 bytes）；审计开始时 0 MiB 占用。
- 项目 Python：`/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python`，Python 3.12.13。
- PyTorch：2.8.0+cu128；`torch.version.cuda=12.8`。
- GPU 可用：`torch.cuda.is_available()=True`；compute capability 12.0；BF16 可用，BF16 CUDA matmul 为有限值。
- LeRobot 0.6.2，源码 commit `22bd7a2f489b367d8df42de803b1e8c4ca63a3f9`；`hf-libero=0.1.4`、`robosuite=1.4.0`、`mujoco=3.8.1`、`torchcodec=0.7.0`。
- `/root/autodl-tmp/vla_env.sh` 存在，且其 `VLA_PYTHON` 指向上述项目专用 Python。

系统默认 `python` 未加入 PATH，但项目环境入口明确使用 `VLA_PYTHON`，因此不阻塞当前项目；不应在未经需要时修改系统 Python。

## 资产完整性

已确认迁移后仍存在并可读取：

- 项目目录约 34 GB，项目 Python 环境约 9.5 GB，缓存约 21 GB。
- 训练目录 `results/training/pi05_expert_first_stage_2k/` 约 22 GB，含 `train.log`、2000-step `torch_step_metrics.jsonl`、GPU 时序、显存/时间摘要、训练配置和 checkpoint manifest。
- checkpoint `001000` 与 `002000` 均存在；每个包含 `config.json`、训练配置、tokenizer、processor、normalizer/unnormalizer 与约 9.35 GB 的 `model.safetensors`。
- 两个 checkpoint 导入 `lerobot.policies.pi05` 后均能被 `PreTrainedConfig` 正常解析为 `PI05Config`；配置为 `chunk_size=50`、`n_action_steps=10`、BF16、7D action、两路视觉输入和 8D state。
- LIBERO dataset metadata 位于 `/root/autodl-tmp/cache/huggingface/lerobot/lerobot/libero/meta/info.json`；`/root/.libero/config.yaml` 仍存在。
- 既有 evaluation summary、checkpoint progression、fixed-state/generalization、failure analysis、Phase 2/3 结果和现有视频均存在。

远程克隆目录本身不是 Git worktree；这不影响 runtime 或 checkpoint 加载。远程 `assets/figures/` 未找到，而本地项目中已有五张 SVG 图表；这是展示资产同步差异，未重新生成或覆盖，后续同步前应先核对来源与 hash。

## 硬编码审计

项目自有配置正常使用 `/root/autodl-tmp`、缓存路径和 checkpoint/result 路径，这是远程持久化目录约定，不是旧实例专属路径。上游 LeRobot 源码中出现的 `RTX 4090`、`HF_HOME` 等主要为文档、Docker 或 CI 示例。未发现项目 runtime 对 RTX 6000D、RTX 4090、CUDA architecture 或 compute capability 的强制绑定。

## 最小 Smoke Test

新增脚本：`scripts/check_5090_migration.py`。

独立输出目录：`results/migration_smoke_5090_20260813/`。脚本在创建目录前拒绝覆盖；没有创建 optimizer、没有 backward、没有 `env.step()`。

- 加载 checkpoint：`002000/pretrained_model` 成功。
- LIBERO：`libero_10` task 0 成功初始化与 reset。
- 指令：`put both the alphabet soup and the tomato sauce in the basket`。
- 原始 observation：两路 `pixels`（`image`、`image2`）和 `robot_state`（`eef`、`gripper`、`joints`）。
- 经 LeRobot 的实际 LIBERO processor 后：两路 `[1,3,360,360]` float32 图像和 `[1,8]` float32 state，均有限。
- 经 checkpoint preprocessor 后：图像/state 在 `cuda:0`，语言 tokens 为 `[1,200]`，无 device/dtype mismatch。
- 一次真实 `predict_action_chunk`：成功，输出 `[1,50,7]` float32，所有数值有限。
- 单次调用延迟：556.762 ms；仅用于迁移 smoke test，不与历史正式 profiling 混用。
- peak allocated/reserved：9,524,050,432 / 9,877,585,920 bytes（约 8.87 / 9.20 GiB）。
- OOM：否；CUDA 错误：无；环境 action：未执行。
- 全流程 wall time：131.663 s，主要包含模型加载。

## RTX 6000D 与 RTX 5090 对照

| 项目 | RTX 6000D 已有正式记录 | RTX 5090 本次实际验证 |
| --- | --- | --- |
| GPU 显存 | 85,651 MiB | 32,607 MiB |
| PyTorch / CUDA runtime | 2.8.0+cu128 / 12.8 | 2.8.0+cu128 / 12.8 |
| checkpoint | 2k 可加载 | 2k 可加载并完成真实推理 |
| BF16 | 已使用 | 支持并成功推理 |
| `predict_action_chunk` | 300 次正式 profiling mean 182.876 ms | 仅一次 smoke：556.762 ms，不可比较 |
| 推理峰值显存 | 约 8.87 / 9.20 GiB allocated/reserved | 约 8.87 / 9.20 GiB allocated/reserved |

## 结论

迁移成功。RTX 5090 已在真实 LIBERO observation 和 2k Pi0.5 checkpoint 路径上完成无动作、无污染的端到端推理验证。当前没有 GPU 兼容性、BF16、dtype、device mismatch 或 OOM 阻塞。

若只能选一个下一步，优先做**更规范的 RTX 5090 inference profiling**：在完全独立的诊断目录中使用固定协议完成 warm-up 后的多次 `predict_action_chunk` 计时与显存记录。它能回答新硬件的实际部署性能，同时不重跑、改写或混淆已冻结的 Phase 1/Phase 3 成功率结论。
