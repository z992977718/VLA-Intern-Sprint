# 新增评测固定初态

## 协议有效性

`libero_10` task 0 有 50 个存储 `.pruned_init` row。此前统一评测使用 index 0–29。本次在第一次 reset 前将项目侧同步环境的 `init_state_id` 设置为 30，之后保持 LeRobot 环境不变，让它正常推进至 49。

结果文件在每个 episode 中记录 `init_state_id`，确认正好使用 20 个唯一 ID（30–49），与 0–29 无重叠。没有修改 LeRobot 或 LIBERO 上游源码。

这些是此前未评测的固定初态：它们未出现在早期 0–29 评测中，但无法证明没有出现在模型训练中。`pi05_libero_base` provenance 和本地 demonstration metadata 都没有 state-level training-exposure manifest。

## 固定设置

| 项目 | 数值 |
| --- | --- |
| Checkpoint | `002000/pretrained_model` |
| Suite / task | `libero_10`，task ID 0 |
| 指令 | `put both the alphabet soup and the tomato sauce in the basket` |
| Init-state ID | 30–49 |
| Seed label | 1030–1049 |
| Episodes | 20，顺序运行，batch size 1 |
| Horizon | 520 control steps |
| 控制 | 相对 7 维 action |
| Action chunk 执行 | `n_action_steps=10` |
| Observation | 两路 360×360 RGB 相机 + robot state；policy resize 224×224 |
| 精度 | BF16，`use_amp=false` |
| Success | LIBERO `check_success()` |

## 结果

| 指标 | 初态 0–29 | 新增评测状态 30–49 | 全部 50 个固定状态 |
| --- | ---: | ---: | ---: |
| Success | 28/30（93.33%） | 18/20（90.0%） | 46/50（92.0%） |
| 平均 episode 长度 | 291.13 | 304.35 | 296.42 |
| 中位 episode 长度 | 266.5 | 282.0 | 270.0 |
| 失败 | state 14、18 | state 41、49 | 4 |

新增 20 episodes 的 95% Wilson interval 为 69.9%–97.2%，全部 50 个固定状态为 81.2%–96.8%。这些区间说明 18/20 应被理解为较强的同任务鲁棒性证据，而不是精确的通用成功率。

新增运行的其他测量：

- mean / median / p95 模型推理：172.373 / 160.608 / 217.453 ms；
- evaluation wall time：334.17 秒；
- 峰值 allocated / reserved VRAM：8.870 / 9.199 GiB；
- OOM：否；
- 已保存 20 个视频、20 行 episode 数据和 init-state ID 30–49。

## 结论

Checkpoint 002000 在该单一重点任务的全部存储初态上保持较强表现：总体 46/50，此前未评测状态为 18/20。这支持该任务在 benchmark 固定初态集合上的同任务鲁棒性，不支持 training-unseen state、cross-task、语言、相机、物体布局或 open-world generalization 结论。

原始证据：`heldout_initial_states/`。
