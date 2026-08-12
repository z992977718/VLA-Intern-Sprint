# 最终项目事实

本文件是 Phase 1 收尾阶段冻结后的唯一事实来源。下列指标均来自项目中保存的日志、JSON 或 CSV，不得将结论扩大到既定实验协议之外。

## 1. 环境

- 执行边界：本地 Windows 只用于源码、脚本、笔记、Git 和结果管理；VLA 运行工作只在远程 Linux 执行。
- GPU：NVIDIA RTX 6000D；`nvidia-smi` 报告 85,651 MiB，PyTorch 报告 83.04895 GiB。
- Driver：595.71.05；driver capability 报告 CUDA 13.2。
- Runtime：Python 3.12.13、PyTorch 2.8.0+cu128、torchvision 0.23.0+cu128、TorchCodec 0.7.0、FFmpeg 7.1.1、hf-libero 0.1.4。
- LeRobot：0.6.2，commit `22bd7a2f489b367d8df42de803b1e8c4ca63a3f9`。
- 无界面 MuJoCo 渲染：`MUJOCO_GL=egl`。

## 2. 数据集

- 仓库：`lerobot/libero`。
- 固定 revision：`a1aaacb7f6cd6ee5fb43120f673cebb0cfea7dd4`。
- 规模：40 tasks、1,693 episodes、273,465 frames。
- 包含 suite：LIBERO-Spatial、LIBERO-Object、LIBERO-Goal、LIBERO-10，每个 suite 10 个任务。
- Observation schema：两路 256×256 RGB 视频和 8 维 state。
- Action schema：7 维连续 action。
- 实际训练命令使用完整数据集 split，没有 task filter。这不是单任务微调。

## 3. 模型

- Policy：LeRobot 实现的 Pi0.5。
- 起始 checkpoint：`lerobot/pi05_libero_base`，不是 `pi05_base`。
- 当前 LeRobot 文档将该 checkpoint 描述为专门在 LIBERO 上训练；检查过的文件中没有它精确到样本级别的训练暴露信息。
- 模型输入：两张图像、8 维 robot state 和语言指令。
- 模型输出：内部为 50-step action chunk；评测每次执行其中 10 个动作后重新调用模型。
- 重点评测任务：`libero_10` task ID 0。
- 指令：`put both the alphabet soup and the tomato sauce in the basket`。
- 该指令在 40 任务训练数据中为 `task_index=5`。

## 4. 训练

- 在完整 40 任务数据集上持续微调 2,000 个 optimizer steps。
- Batch size 1；BF16 policy 和 BF16 mixed precision。
- `train_expert_only=true`；冻结 vision encoder。
- 开启 gradient checkpointing；关闭 compile、EMA、在线评测、W&B 和 Hub push。
- 可训练参数 / 总参数：693,422,112 / 4,143,404,816。
- 记录的 2,000 个 loss 均为有限值，无 OOM。
- 首个 / 最终记录 loss：1.470371 / 0.204011。
- 平均 / 中位 step 时间：0.223727 / 0.209552 秒。
- Wrapper 总运行时间包含模型加载和两次 checkpoint 写入：578.463 秒（9.64 分钟）。
- 保存 checkpoint：001000 和 002000。

## 5. Pretrained 基线

- Checkpoint：`lerobot/pi05_libero_base`。
- 协议：`libero_10` task 0、固定初态 ID 0–9、10 episodes、520-step horizon、batch size 1、hard reset、relative control、BF16、`n_action_steps=10`。
- 结果：0/10；所有 episode 均达到 520 steps。
- 平均 / 中位 / p95 模型推理延迟：181.610 / 170.294 / 221.990 ms。
- 这是重点任务的基线结果，不是完整 LIBERO 分数。

## 6. 1k Checkpoint

- Checkpoint 001000 在固定初态 ID 0–9 上为 9/10（90%）。
- 平均 / 中位 episode 长度：290.0 / 273.0。
- 平均 / 中位 / p95 推理延迟：170.677 / 160.998 / 207.672 ms。
- 唯一失败：固定状态 4，在 520 steps 时耗尽 horizon。
- 视频显示 policy 反复接近或接触目标，但没有形成稳定抓取与搬运。

## 7. 2k Checkpoint

- 匹配固定状态 0–9：10/10，平均 episode 长度 271.9。
- 统一评测固定状态 0–29：28/30（93.33%）。
- 状态 0–29 的平均 / 中位 episode 长度：291.133 / 266.5。
- 状态 0–29 的平均 / 中位 / p95 推理延迟：168.289 / 160.091 / 206.702 ms。
- 状态 0–29 中失败的状态：14 和 18。
- 统一评测的前十行在 success flag 和 episode length 上完全复现了此前的 10-episode 2k 结果。

## 8. 50 个固定初态评测

- 该任务包含 50 个按完整行 hash 确认唯一的 `.pruned_init` 存储状态。
- 早期评测：ID 0–29，28/30。
- 新增、此前未评测的固定初态：ID 30–49，18/20。
- 全部固定初态结果：46/50（92.0%）。
- 合并后的平均 / 中位 episode 长度：296.42 / 270.0。
- 失败状态：14、18、41、49。
- 无法证明 ID 30–49 是 training-held-out 或训练阶段未见状态。

## 9. 延迟

- 延迟测量真实 `predict_action_chunk` 调用，调用前后立即执行 CUDA synchronization。
- Pretrained，10 episodes：mean 181.610 ms，p95 221.990 ms。
- 1k，10 episodes：mean 170.677 ms，p95 207.672 ms。
- 2k，状态 0–29：mean 168.289 ms，p95 206.702 ms。
- 2k，新增状态 30–49：mean 172.373 ms，p95 217.453 ms。
- 从缓存 action deque 取动作的操作不计入模型推理调用。

## 10. 显存

- 训练峰值 allocated / reserved：12.8482 / 13.0039 GiB。
- 评测峰值 allocated / reserved：约 8.8700 / 9.1992 GiB。
- 训练和评测均未发生 OOM。
- 这些是 RTX 6000D、batch size 1 下的实测值，不是通用硬件要求。

## 11. 失败案例

- 1k state 4：观察到抓取建立失败和反复重试。
- 2k state 14、18、41、49：每个被审查的失败都明显涉及错误物体选择或放置；部分还涉及杂物碰撞。
- 可观察事实：policy 操作或放置了非目标物，并在 horizon 前未完成两个指定目标的放置。
- 仅为可能解释：视觉目标选择、语言条件或恢复行为可能参与其中。
- 未被证明：VLM 内部语义或语言理解缺陷。

## 12. 局限性

- 只有一个重点任务接受了深入 checkpoint 和 50-state 评测。
- 未执行完整的 400-episode、四 suite LIBERO benchmark。
- 未测量 cross-task retention / transfer。
- 本次 2k 训练没有从 40 任务数据集中排除任何任务。
- 起始 checkpoint `pi05_libero_base` 已有 LIBERO exposure。
- 固定状态 30–49 仅在早期 0–29 评测中尚未被评测；它们的训练暴露未知。
- 未使用 LIBERO-plus 扰动、Isaac Sim、ROS 2 或真实机器人。
- 不存在 open-world 或 real-world generalization 结果。

## 13. 可以做出的声明

- 复现 LeRobot Pi0.5 + LIBERO Linux GPU 运行环境，并完成真实 forward、backward 和 optimizer step 训练。
- 在固定 revision 的 40 任务 LIBERO 数据集上，对 `pi05_libero_base` 持续微调 2,000 steps。
- 建立可复现的 closed-loop evaluation 与 latency profiling 协议。
- 在重点任务匹配固定状态 0–9 上，pretrained 为 0/10、1k 为 9/10、2k 为 10/10。
- Checkpoint 2k 在该重点任务的 50 个存储固定初态上成功 46 次。
- 四个被审查的 2k 失败均出现 wrong-object-selection behavior。
- 将训练 loss 和 Rollout success 作为不同指标分别分析。

## 14. 不能做出的声明

- “LIBERO 成功率为 92%。”
- “Pi0.5 实现了 unseen-task 或 open-world generalization。”
- “状态 30–49 在训练阶段未见。”
- “项目完成了完整 LIBERO benchmark。”
- “本次运行是单任务微调。”
- “发生 catastrophic forgetting”或“实现 positive cross-task transfer”。
- “已经证明 VLM 语义模块存在故障。”
- “本项目从零实现了 Pi0.5、LeRobot 或 LIBERO 算法。”
- “工业级部署”或“真实机器人验证”。
