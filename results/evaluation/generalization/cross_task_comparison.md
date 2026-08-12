# 跨任务对比

## 状态：Training exposure audit 后跳过

原计划假设可以从同一 LIBERO suite 中选出三个没有参与 task-specific fine-tuning 的任务，但实际训练不符合该前提：

- 数据集：完整 `lerobot/libero` revision `a1aaacb7f6cd6ee5fb43120f673cebb0cfea7dd4`；
- 数据集元数据：40 tasks、1,693 episodes；
- 实际 task filter：无；
- `libero_10` task 0 指令在数据集中为 task index 5；
- 四个 10-task suite 中的其他任务也全部列于 `meta/tasks.parquet`。

因此该数据集中不存在符合条件的 `unseen-to-this-finetuning` 任务。让 pretrained 和 2k 在另外三个 `libero_10` 任务上运行，只能测量额外多任务训练后的不同任务性能，而不是单任务适配产生的迁移。它可以作为单独的 retention study，但不能回答原问题，所以本项目没有静默替换实验定义。

## 原计划 A/B/C 迁移结果

不分配 A/B/C transfer label。本阶段没有 cross-task Rollout 结果，因此证据不能证明：

- 对 2k 训练中被排除任务的 pretrained 能力保留情况；
- 对训练中被排除任务的过拟合或 catastrophic forgetting；
- 对训练中被排除任务的 positive transfer。

起始 checkpoint 也是 `pi05_libero_base`，当前 LeRobot 文档将其描述为专门在 LIBERO 上训练。没有更详细 exposure manifest 时，不能把 vanilla LIBERO 任务称为起始 checkpoint 从未见过的任务。

机器可读状态：`cross_task_results.csv`。
