# 简历版本

## A. 两行精简版

- 基于 LeRobot 在 RTX 6000D 上复现 Pi0.5 + LIBERO 训练评测环境，使用完整 40 任务数据集（1,693 episodes / 273,465 frames）对 `pi05_libero_base` 进行 2,000-step expert-only continued fine-tuning，并完成 1k/2k checkpoint 管理。
- 构建重点任务闭环 Rollout 与 CUDA 同步延迟评测协议；在该任务全部 50 个固定初态上实现 46/50，2k 30-episode 推理均值 168.3 ms，并通过视频归纳出 4 个 wrong-object-selection 失败案例。

## B. 三至四行详细版

- 使用 LeRobot、Pi0.5 与 LIBERO 搭建可复现的远程 Linux GPU 实验链路，固定 LeRobot 0.6.2 与数据集 revision，完成模型、数据、MuJoCo/EGL、TorchCodec 和 CUDA 环境验收。
- 基于 `lerobot/pi05_libero_base` 在完整 40 任务 LIBERO 数据集（1,693 episodes、273,465 frames）执行 2,000-step BF16 continued fine-tuning，采用 batch size 1、expert-only、冻结 vision encoder 与 gradient checkpointing；训练峰值显存 12.85 GiB、无 OOM。
- 设计 fixed-initial-state 闭环评测与 checkpoint progression：重点任务 pretrained 0/10、1k 9/10、2k 28/30；进一步覆盖全部 50 个固定初态，2k 获得 46/50 的同任务固定初态结果。
- 对 `predict_action_chunk` 实施 CUDA 同步延迟分析（2k 30-episode mean/p95 168.3/206.7 ms），结合 Rollout 视频审计 4 个错误物体选择案例，并明确区分可观察行为、可能原因和无法支持的泛化结论。

## 定制时的表述边界

不得将上述内容改写为：

- “LIBERO success rate 92%”;
- “single-task fine-tuning”;
- “unseen-state/open-world generalization”;
- “full Pi0.5 reproduction”;
- “industrial or real-robot deployment.”
