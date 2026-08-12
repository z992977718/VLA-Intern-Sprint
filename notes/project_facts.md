# 项目事实

## 当前阶段

```text
Phase 1: π0.5 + LeRobot + LIBERO — DONE
Phase 2: Isaac Sim + ROS 2 + Manipulator Deployment — IN PROGRESS
```

- Phase 1 已冻结：不得修改实验结果、重新训练 Pi0.5、启动 LIBERO Rollout，或删除 checkpoint/原始实验数据。
- Phase 2 / Step 1 的唯一运行目标是建立 ROS 2 joint command → Isaac Sim Franka articulation → ROS 2 joint-state feedback 的最小闭环；禁止接入 Pi0.5、Camera、MoveIt 或抓取。
- Phase 2 / Step 1 已于 2026-08-12 通过：Isaac Sim 6.0.1、ROS 2 Humble、官方 Franka Panda、physics、ROS 2 Bridge、`/joint_command` 与 `/joint_states` 均完成真实闭环验证。
- 最终一键复现的 Franka 七轴初始/目标/结果分别为 `[0.012,-0.5686,0,-2.8109,0,3.0368,0.741]`、`[0,-0.45,0,-1.75,0,1.3,0.78]`、`[0.0001,-0.4489,0,-1.7715,0,1.3560,0.7796]`，最大误差 0.0560 rad。
- Step 1 RTX 场景 peak GPU VRAM 实测为 577 MiB，OOM=NO；该值不外推到 Camera、VLA 或更复杂场景。
- Remote visualization 为 NOT CONFIGURED；这不影响已由关节数值证据验证的 headless 仿真执行。

- 当前主要 VLA 模型是 Pi0.5；SmolVLA 是可选 baseline。
- 项目使用 LeRobot `0.6.2`，commit 为 `22bd7a2f489b367d8df42de803b1e8c4ca63a3f9`。
- 本地 Windows 仅用于 Codex、Git、源码阅读、脚本、笔记和结果索引；VLA runtime 只在远程执行。
- 主要远程 GPU 为 NVIDIA RTX 6000D，`nvidia-smi` 报告 85,651 MiB VRAM。
- 主要持久化数据根目录为 `/root/autodl-tmp`，容量 150 GB。
- 已验证 runtime：Python 3.12.13、PyTorch 2.8.0+cu128、torchvision 0.23.0+cu128、TorchCodec 0.7.0、FFmpeg 7.1.1、hf-libero 0.1.4。
- LIBERO `libero_10` task 0 可以初始化、reset、返回 `pixels` 和 `robot_state`、暴露 7 维 action 并正常关闭。
- 2026-08-11 完成 20-step Pi0.5 LIBERO sanity training：batch size 1、BF16、gradient checkpointing、expert-only、冻结 vision encoder。
- Sanity run 峰值 allocated/reserved 显存为 12.8482/13.0039 GiB，loss 有限、无 OOM，并保存 step-20 checkpoint。
- Sanity run 平均 step 为 0.4728 秒（包含首批加载），steps 2–20 平均为 0.2454 秒。这不是 Rollout latency 或正式训练吞吐结论。
- 正式 2,000-step Pi0.5 expert-only 第一阶段完成，配置为 batch size 1、BF16、gradient checkpointing，并保存 1k/2k checkpoint。峰值显存 12.8482/13.0039 GiB，无 OOM。
- 在固定匹配协议（`libero_10` task 0、seeds 1000–1009）中，pretrained 为 0/10，2k 为 10/10。这是单个重点任务的结果，不是完整 LIBERO 分数。
- Pretrained 与 2k 平均模型推理延迟分别为 181.61 ms 和 168.99 ms；两者都使用 BF16 和 `n_action_steps=10`。
- 项目已在计划的 2k 决策点停止，没有执行 5k/10k 或完整 LIBERO evaluation。
- 旧 RTX 4090 数据已在迁移后通过 hash 验证，该服务器可以保持关机。
- Checkpoint 001000 在固定初态 0–9 上为 9/10，唯一失败为 state 4 达到 520-step horizon。
- Checkpoint 002000 在连续一次运行中覆盖唯一固定初态 0–29，结果 28/30；失败为 state 14 和 18，无 OOM。
- 2k 统一运行的前十个 episode 完全复现早期十集的 success flag 和 episode length。匹配前十个状态上，1k 为 9/10，2k 为 10/10。
- 在此协议中，episode seed label 不负责选择 fixed init state。每个新评测进程中，LeRobot 从 `.pruned_init` index 0 开始依次推进；重启进程会重新从该 index 开始。
- 该任务有 50 个按完整行 hash 验证唯一的存储 init-state row。固定同一 row 但改变 seed 时，测得首个 observation 相同；连续存储 row 会改变 pixels 和 robot state。
- 扩展后的 2k 结果支持同任务 fixed-initial-state 稳定性，不支持 unseen-seed、unseen-layout、完整 LIBERO 或泛化结论。
- 视频审查发现 1k 有一次 grasp-acquisition/retry failure；2k 状态 14、18 出现明显 wrong-object-selection failure。因未记录内部 policy signal、contact 或 object-ID log，根因解释仍是假设。
- 前 30 个固定状态后选择决策 B：保留 checkpoint 002000，并在增加训练步数前做有意义的额外条件检查。随后已评测固定状态 30–49，没有继续训练。
- Training exposure audit 纠正了实验描述：实际 2k run 使用完整 `lerobot/libero` 的 40 个任务，没有 task filter，不是针对 `libero_10` task 0 的 task-specific fine-tuning。
- 固定训练数据包含 1,693 episodes、273,465 frames 和 40 tasks。重点 task-0 指令在数据集中是 `task_index=5`。
- 起始 checkpoint 为 `lerobot/pi05_libero_base`；当前 LeRobot docs 将其描述为专门在 LIBERO 上训练，精确样本级 exposure 未由所检查文件公开。
- 40 任务数据集中没有任务对本次 2k fine-tuning 属于 unseen。原计划的 60-episode cross-task transfer comparison 因此被跳过，不存在 retention/transfer 结论。
- 此前未评测的固定初态 ID 30–49 在 checkpoint 002000 下为 18/20，mean/median length 304.35/282.0，无 OOM。
- 全部固定状态 0–49 上 checkpoint 002000 为 46/50（92.0%）。这是同任务 fixed-initial-state robustness，不证明这些状态未参与模型训练。
- 50 个状态中的四个 2k 失败均明显涉及错误物体选择；不能证明内部 language/VLM root cause。
- Phase 1 实验已完成。下一步是整理 README 和面试材料；LIBERO-plus 保持可选且未安装。
