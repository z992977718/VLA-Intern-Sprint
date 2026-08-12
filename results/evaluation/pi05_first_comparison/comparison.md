# Pi0.5 首次配对对比

## 结果

| 指标 | Pretrained baseline | 2k expert-only checkpoint | 变化 |
| --- | ---: | ---: | ---: |
| Success | 0/10（0.0%） | 10/10（100.0%） | +100.0 个百分点 |
| 平均 episode 长度 | 520.0 | 271.9 | -248.1 steps |
| 平均模型推理 | 181.61 ms | 168.99 ms | -12.62 ms |
| p95 模型推理 | 221.99 ms | 208.34 ms | -13.65 ms |
| Evaluation wall time | 274.05 秒 | 153.32 秒 | -120.73 秒 |
| 峰值 allocated VRAM | 8.87 GiB | 8.87 GiB | +0.00 GiB |

配对协议使用 `libero_10` task 0、seeds 1000–1009、BF16、`n_action_steps=10`、固定 initial states、hard reset 和 520-step limit。所有 baseline episode 都超时，所有 2k-checkpoint episode 均在 227–370 steps 内成功。

## 训练证据

- 完成 2,000/2,000 optimizer steps，batch size 1；
- Expert-only、冻结 vision encoder、gradient checkpointing、BF16；
- 首个 profiled loss 1.470371，最终 profiled loss 0.204011；
- 所有 loss 有限：`true`；OOM：`false`；
- 平均 step 时间 0.2237 秒，wrapper 总运行时间 578.46 秒；
- 峰值 allocated/reserved training VRAM：12.85/13.00 GiB。

## 解释

2k checkpoint 在这个特定配对任务上明显优于 pretrained baseline。Training loss 变化与 success rate 变化是两项独立观察：loss 是离线优化信号，success 是闭环环境结果。较低 loss 本身不能证明 Rollout 改善；直接证据是配对的 0/10 与 10/10 Rollout。

这不是完整 LIBERO benchmark，只覆盖十个 LIBERO-Long 任务中的一个，因此不能报告为“LIBERO 成功率 100%”。

## 决策

在计划决策点停止。保留 RTX 6000D 和 1k/2k checkpoint，不自动继续 5k 或 10k；下一项实验只有在检查本报告与视频后才能决定。
