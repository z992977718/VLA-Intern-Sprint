# Pi0.5 Expert-only 第一阶段计划

## 目的

在 pretrained baseline 后运行第一次有明确边界的正式 fine-tuning，然后停止并进行配对闭环评测。这不是官方 30k-step 复现，不得自动延长。

## 源码与文档依据

- 当前 LeRobot Pi0.5 文档提供低显存 expert-only recipe：`freeze_vision_encoder=true`、`train_expert_only=true`、`gradient_checkpointing=true`、`dtype=bfloat16`；
- 官方完整 recipe 为 30,000 steps；本项目刻意把 2,000 steps 设为第一个决策点；
- `lerobot/libero` 包含 40 tasks、1,693 episodes、273,465 frames。在 batch size 1 下，2,000 optimizer steps 只是早期适配阶段，不等价于完整 epoch training；
- RTX 6000D 上的 20-step sanity run 已用该低显存配置验证 forward、backward 和 optimizer step。

## 固定训练配置

| 项目 | 数值 |
| --- | --- |
| Pretrained policy | 本地已验证 `lerobot/pi05_libero_base` snapshot |
| Dataset | 本地 `lerobot/libero`，revision `a1aaacb7f6cd6ee5fb43120f673cebb0cfea7dd4` |
| Steps | 2,000 |
| Batch size | 1 |
| 精度 | Policy BF16 和 Accelerate mixed precision BF16 |
| 可训练范围 | 仅 expert 和 projection |
| Vision encoder | 冻结 |
| Gradient checkpointing | 开启 |
| EMA / compile | 关闭 / 关闭 |
| Normalization | State/action 使用 mean/std，visual 使用 identity |
| Optimizer / scheduler | 当前 Pi0.5 policy 默认值；scheduler 自动缩放到 2k horizon |
| Seed | 1000 |
| 训练期间在线评测 | 关闭 |

## Checkpoint 与磁盘策略

只在 step 1,000 和 2,000 保存。根据实测 sanity checkpoint，每个包含 optimizer state 的 checkpoint 约 11 GiB，因此本阶段约新增 22 GiB。Preflight 要求至少 60 GiB 可用空间，并拒绝与其他 GPU process 重叠。首次对比前保留两个 checkpoint；不创建 500-step checkpoint，也不删除已有 20-step sanity evidence。

Step 2,000 后，只使用固定配对协议评测 `002000/pretrained_model`，生成对比后停止。
