# 训练暴露审计

## 结果

2,000-step run 不是针对 `libero_10` task 0 的 task-specific fine-tuning，而是在包含 40 个任务的完整本地 `lerobot/libero` 数据集上继续训练。实际命令中没有 dataset task filter。因此同一四-suite 数据集中不存在原计划要求的三个 `unseen-to-this-fine-tuning` 任务，所提议的 60-episode cross-task 实验未执行。

## 实际微调配置

| 项目 | 已验证数值 |
| --- | --- |
| Dataset | `lerobot/libero` |
| Dataset revision | `a1aaacb7f6cd6ee5fb43120f673cebb0cfea7dd4` |
| Dataset split | 全部 `0:1693` training episodes |
| Dataset scope | 1,693 episodes、273,465 frames、40 tasks |
| Dataset task filter | 无 |
| 起始 checkpoint | `lerobot/pi05_libero_base` 的本地已验证 snapshot |
| Training steps | 2,000 |
| Training mode | expert-only、冻结 vision encoder、BF16、batch size 1 |

实际命令使用 `--dataset.repo_id=lerobot/libero`，将 `--dataset.root` 指向完整数据集根目录，没有传入 episode 或 task filter。`meta/tasks.parquet` 包含 40 行语言指令；当前评测指令在元数据中为 dataset `task_index=5`：

```text
put both the alphabet soup and the tomato sauce in the basket
```

另外九个 `libero_10` 指令，以及 `libero_spatial`、`libero_object`、`libero_goal` 的全部 30 个指令，也都存在于同一个 40 行元数据表中。因此另一个 `libero_10` 任务可以是不同评测任务，但不是从本次 2k fine-tuning 数据中排除的任务。

## 已评测任务

| 字段 | 数值 |
| --- | --- |
| Suite | `libero_10` / LIBERO-Long |
| Suite task ID | 0 |
| 语言指令 | `put both the alphabet soup and the tomato sauce in the basket` |
| Dataset task index | 5 |

把它称为“训练任务”并不准确：它是 40 个训练数据任务之一，也是目前唯一深入评测的任务。

## Pretrained checkpoint 身份与先前暴露

起始 checkpoint 为 `lerobot/pi05_libero_base`，不是 `pi05_base`，也不是后来的 `pi05_libero_finetuned`。本地 snapshot config 显示 `type=pi05`、两路 256×256 图像输入、8 维 state、7 维 action、`chunk_size=50`、`n_action_steps=10`。

当前 LeRobot `docs/source/pi05.mdx` 明确将 `lerobot/pi05_libero_base` 列为专门在 Libero dataset 上训练的模型，并称其为用于继续在 `lerobot/libero` 上 fine-tuning 的 LIBERO base model。因此，没有更细 exposure manifest 时，不能把其他 vanilla LIBERO task 描述为起始模型从未见过。公开材料没有提供该 base checkpoint 的 per-episode 或 per-init-state exposure manifest，所以只能确认 dataset-level LIBERO exposure，无法确认精确训练样本。

## 对本阶段的影响

- 有效：评测此前 30-episode 重点任务实验未使用的存储 init state 30–49。
- 无效声明：这些状态必然在模型训练期间未见，因为不存在 training-state manifest。
- 无效的原计划对比：三个未参与本次 2k fine-tuning 的任务，因为运行使用了全部 40 个 dataset tasks。
- 未执行：60 个 cross-task episodes，因为它们不能回答原定 unseen-to-fine-tuning transfer 问题。

## 已检查证据

- `results/training/pi05_expert_first_stage_2k/training_config.txt`
- `scripts/run_pi05_first_stage_2k.sh`
- 本地数据集 `meta/info.json` 和 `meta/tasks.parquet`
- 本地 `pi05_libero_base/config.json` 和模型 README
- 当前 `lerobot/docs/source/pi05.mdx`
- 当前 `lerobot/docs/source/libero.mdx`
