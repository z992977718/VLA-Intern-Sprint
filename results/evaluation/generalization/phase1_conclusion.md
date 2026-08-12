# Phase 1 最终结论

## 直接回答

### 1. Checkpoint 002000 使用什么数据训练？

它在完整 40 任务 `lerobot/libero` 数据集上额外训练 2,000 steps，revision 为 `a1aaacb7f6cd6ee5fb43120f673cebb0cfea7dd4`，没有 task filter。因此这是多任务 continued fine-tuning，不是对 `libero_10` task 0 的 task-specific fine-tuning。

本项目评测的是 `libero_10` task ID 0，指令为 `put both the alphabet soup and the tomato sauce in the basket`。它是数据集 task index 5，也是全部 40 个训练数据任务之一。

### 2. 重点评测任务有多稳定？

Checkpoint 002000 在固定初态 0–29 上为 28/30，在 30–49 上为 18/20，在完整存储 fixed-state set 上合计 46/50（92.0%）。仍有四次失败，因此这是较强但并非无失败的同任务稳定性。

### 3. 新增评测的固定初态表现如何？

状态 30–49 为 18/20（90.0%），mean/median length 为 304.35/282.0。两个失败都达到 520-step horizon，无 OOM 或 runtime anomaly。相对早期 0–29 评测，它们是此前未评测的固定初态，但不能证明为 training-held-out。

### 4. 本次 fine-tuning 未使用的三个任务表现如何？

不适用：2k run 使用的数据集内部不存在这样的任务。训练使用完整 40-task dataset 且无过滤，因此没有执行原计划的 60 episodes。人为挑选三个所谓 `unseen-to-finetuning` 任务会产生标签错误的结果。

### 5. 与 pretrained 相比，是保持、退化还是正迁移？

没有测量 cross-task retention 和 transfer，因此不作相关声明。在匹配的重点任务固定状态 0–9 上，pretrained 为 0/10，checkpoint 002000 为 10/10，可以直接支持该任务在该协议下有所改善；但不能把原因解释成单任务适配，因为 2k 数据包含 40 个任务。

当前没有 catastrophic forgetting、能力退化或 held-out task positive transfer 的证据。这些假设需要重新定义实验。

### 6. 证据支持什么级别的结论？

- **重点任务适配：** 匹配状态 0–9 从 pretrained 0/10 提高到 2k 10/10，但因为 2k 数据覆盖 40 tasks，不能归因于单任务训练。
- **同任务 initial-state 鲁棒性：** 全部 50 个存储固定状态为 46/50，获得支持。
- **Cross-task transfer/retention：** 未建立；实验设计中没有符合要求的 held-out task。

证据不支持 Pi0.5 实现通用 LIBERO、open-world、unseen-task generalization，也不支持报告完整 benchmark 百分比。

## 最终摘要

```text
训练暴露：
pretrained checkpoint = lerobot/pi05_libero_base
fine-tuning suite = lerobot/libero 中由 libero_spatial、libero_object、
                    libero_goal、libero_10 组成的全部 40 tasks
fine-tuning task = 不是单个任务；重点评测任务为 libero_10 task 0
fine-tuning dataset scope = 1,693 episodes / 273,465 frames / 40 tasks

当前重点评测任务：
2k success = 状态 0-29 上 28/30；全部存储状态上 46/50

新增评测固定初态：
available = yes，此前未评测的固定 ID 30-49
episodes = 20
success = 18/20
conclusion = 较强的同任务 fixed-initial-state robustness；
             未证明 training-unseen generalization

Cross-task：
Task A/B/C = 未选择；不存在对本次 fine-tuning 合格的 unseen task
pretrained episodes = 0
2k episodes = 0

Transfer / retention conclusion：
= 无法由当前训练设计识别

Wrong-object-selection observation：
= 50 个固定状态中的四个 2k 失败均观察到该行为；内部原因未建立

Phase 1 最终结论：
= 多任务 continued fine-tuning 改善了重点评测任务，并取得 46/50 的
  同任务固定状态成功结果；cross-task transfer 未测量
```

## 推荐下一步：A

结束七天实验阶段，整理 README 和面试材料。最有面试价值的教训是 exposure audit：最初被描述为 task-specific 的运行实际是 40-task fine-tuning，因此声称 unseen-task transfer 的实验会无效。

LIBERO-plus 仍可作为后续语言、相机、物体布局、robot-init、光照、背景和传感器噪声 robustness 实验选项，但本阶段未安装或运行。没有启动 5k/10k 训练、Isaac Sim、ROS 2、模型切换或 full fine-tuning。
