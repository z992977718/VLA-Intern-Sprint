# Rollout 视频索引

原始 MP4 文件保留在 `results/evaluation/` 下，本目录只提供索引。这些本地实验视频体积不大，但公开到 GitHub 时应只挑选有代表性的片段，或使用 Release assets / Git LFS，不应重复复制每个 Rollout 视频。

## Pretrained 失败示例

| 示例 | 结果 | 文件 |
| --- | --- | --- |
| Pretrained episode 0 | 重点任务达到 horizon 后失败 | `../../results/evaluation/pi05_pretrained_baseline/videos/eval_episode_0.mp4` |

十个 pretrained 基线 episode 都在 520-step horizon 时失败。Episode 0 是一个能够证明完整 pipeline 正常执行的代表示例，并不表示一种独有失败类型。

## Checkpoint 1k 示例

| 示例 | 结果 | 文件 |
| --- | --- | --- |
| 1k episode 0，固定状态 0 | 成功，311 steps | `../../results/evaluation/pi05_checkpoint_001000/videos/eval_episode_0.mp4` |
| 1k episode 4，固定状态 4 | 失败，520 steps | `../../results/evaluation/pi05_checkpoint_001000/videos/eval_episode_4.mp4` |

1k 失败视频中，可以看到 policy 反复接近或接触目标，但没有形成持续抓取与搬运。

## Checkpoint 2k 成功示例

| 示例 | 结果 | 文件 |
| --- | --- | --- |
| 2k episode 0，固定状态 0 | 成功，287 steps | `../../results/evaluation/pi05_checkpoint_002000_30ep/videos/eval_episode_0.mp4` |
| 2k episode 9，固定状态 9 | 成功，227 steps | `../../results/evaluation/pi05_checkpoint_002000_30ep/videos/eval_episode_9.mp4` |
| 2k 新增 episode 0，固定状态 30 | 成功，239 steps | `../../results/evaluation/generalization/heldout_initial_states/videos/eval_episode_0.mp4` |

## 错误物体选择失败示例

| 固定状态 | 观察到的行为 | 文件 |
| ---: | --- | --- |
| 14 | 放置或操作干扰物，两个目标均未完成 | `../../results/evaluation/pi05_checkpoint_002000_30ep/videos/eval_episode_14.mp4` |
| 18 | 发生杂物碰撞并放置非目标物 | `../../results/evaluation/pi05_checkpoint_002000_30ep/videos/eval_episode_18.mp4` |
| 41 | 将一个非目标小盒子放入篮子 | `../../results/evaluation/generalization/heldout_initial_states/videos/eval_episode_11.mp4` |
| 49 | 将牛奶盒干扰物放入篮子 | `../../results/evaluation/generalization/heldout_initial_states/videos/eval_episode_19.mp4` |

状态 14/18 的 contact sheet 位于 `results/evaluation/pi05_checkpoint_progression/failure_contact_sheets/`，状态 41/49 的 contact sheet 位于 `results/evaluation/generalization/failure_contact_sheets/`。

## 发布建议

- Git 中保留原始日志、CSV/JSON 指标和本索引；
- 仓库只发布少量有代表性的 MP4；
- 如需共享全部 Rollout 视频，使用 Git LFS 或 Release assets；
- 对视频重新编码或剪辑时，必须在本索引中保留原始文件名及 episode/init-state 对应关系。
