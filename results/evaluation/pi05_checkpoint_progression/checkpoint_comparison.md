# Pi0.5 Checkpoint 演进对比

## 固定范围

所有结果都使用 LeRobot `0.6.2` commit `22bd7a2f489b367d8df42de803b1e8c4ca63a3f9`、`libero_10` task 0、batch size 1、固定 LIBERO initial states、hard reset、relative action、520-step horizon、BF16 policy parameter、`use_amp=false` 和 `n_action_steps=10`。Success 由 LIBERO `check_success()` 判定。这是单个重点任务的 checkpoint progression study，不是完整 LIBERO benchmark。

## 结果

| Checkpoint | Episodes | Success | Mean / median length | Length range | Mean / median / p95 inference | Eval VRAM allocated / reserved | OOM |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Pretrained | 10 | 0/10（0.0%） | 520.0 / 520.0 | 520–520 | 181.61 / 170.29 / 221.99 ms | 8.870 / 9.199 GiB | 否 |
| Step 1,000 | 10 | 9/10（90.0%） | 290.0 / 273.0 | 230–520 | 170.68 / 161.00 / 207.67 ms | 8.870 / 9.199 GiB | 否 |
| Step 2,000 | 30 | 28/30（93.3%） | 291.13 / 266.5 | 227–520 | 168.29 / 160.09 / 206.70 ms | 8.870 / 9.199 GiB | 否 |

样本量较小，因此 95% Wilson interval 较宽：pretrained 0.0%–27.8%、1k 59.6%–98.2%、2k 78.7%–98.2%。Point estimate 可以支持工程决策，但不能声称精确总体成功率。

## 匹配的前十个固定初态

1k 与 2k checkpoint 都在 seed label 1000–1009、固定初态 index 0–9 上测试。匹配子集结果：

- 1k：9/10，mean length 290.0；
- 2k：10/10，mean length 271.9；
- fixed state 4 / seed label 1004 从 1k 的 520-step horizon failure 变为 2k 的 315-step success。

新统一 30-episode 2k run 的前十个 episode，在 success flag 和 episode length 上逐集完全复现此前 2k run。这是 fixed-state protocol 可复现的有力证据。

## Training loss 与 Rollout 行为

| Training point | Point loss | 前 100-step mean | 前 100-step range | Rollout 证据 |
| --- | ---: | ---: | ---: | --- |
| 1,000 | 0.199160 | 0.279736 | 0.006355–0.646302 | 固定状态 0–9 上 9/10 |
| 2,000 | 0.204011 | 0.329684 | 0.005704–1.007345 | 状态 0–9 上 10/10；0–29 上 28/30 |

从 1k 到 2k，checkpoint loss 和前 100-step mean 都没有下降，但匹配 Rollout 从 9/10 变为 10/10。Loss 是离线优化信号，success 是闭环任务结果；这项小规模研究不能证明两者单调相关。

## 证据

- Pretrained：`../pi05_pretrained_baseline/`
- 1k：`../pi05_checkpoint_001000/`
- 早期 2k 十集运行：`../pi05_expert_first_stage_2k/`
- 统一 2k 三十集运行：`../pi05_checkpoint_002000_30ep/`
- 机器可读对比：`checkpoint_comparison.csv`
