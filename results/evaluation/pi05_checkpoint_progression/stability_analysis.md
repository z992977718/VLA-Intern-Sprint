# 稳定性与初始状态分析

## 30 个 Episodes 实际改变了什么

Evaluation wrapper 提供 seed label 1000–1029，但这些 label 不负责选择 LIBERO fixed init state。在 batch size 1 下，当前 LeRobot `LiberoEnv` 将 `init_state_id` 从 0 开始，并在每次显式 Rollout reset 时加一。因此，单个不间断的 30-episode 进程会依次评测存储 init-state index 0–29。

当前源码路径：

1. `lerobot_eval.py` 将 `start_seed + episode_index` 传给 reset；
2. `LiberoEnv.reset()` 调用环境 seed 方法并 reset；
3. 随后用 `.pruned_init` 的下一行调用 `set_init_state()`；
4. LIBERO 通过 MuJoCo `sim.set_state_from_flattened()` 应用该扁平状态，推进模拟器并重新生成 observation。

已安装 LIBERO 的 `seed()` 实现只调用 `np.random.seed(seed)`。在实测 fixed-state 检查中，两个新环境使用不同 seed（1000 和 1010）、但相同 fixed init-state index 0 时，两路 RGB 相机和所有 robot-state array 的首个 observation 完全相同。连续两次 reset 使用固定状态 0 与 1 时，pixels 和 robot state 不同。

该任务的 `.pruned_init` 文件有 50 行，全部 50 个 row hash 唯一，本次使用的前 30 行也唯一。每行都是完整的扁平 MuJoCo state，会在随机 seed/reset 阶段后设置模拟配置。Observation 表明这些存储状态会改变场景 pixels 和机器人配置；本研究没有独立分离并量化每个命名物体的 pose component。

机器可读证据：`seed_initial_state_evidence.json`。

## 为什么把 2k 重新运行成单个 30-Episode 进程

附加一个新的 20-episode 进程会让 `init_state_id` 重新从 0 开始并重复固定状态 0–19，即使 seed label 被改变。因此 2k checkpoint 被一次性连续运行 30 episodes，从而无重复地获得固定状态 0–29。该过程没有训练、修改 checkpoint 或改变 policy 配置。

## 稳定性证据

- Step 1,000：9/10；state 4 失败；
- Step 2,000，匹配状态 0–9：10/10；
- Step 2,000，扩展状态 0–29：28/30；state 14 和 18 失败；
- 早期和统一 2k run 对状态 0–9 的 success 与 episode length 完全一致；
- 所有评测均无 OOM；inference VRAM 峰值保持 8.870 GiB allocated、9.199 GiB reserved。

2k checkpoint 在已测 fixed-state set 上可复现且表现较强，但并非无失败。结果支持“一个 LIBERO 任务上的 fixed-initial-state stability”，不支持 unseen-seed、unseen-layout、unseen-task 或完整 LIBERO generalization。
