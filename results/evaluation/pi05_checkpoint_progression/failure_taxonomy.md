# 失败分类

## 方法与证据边界

三个失败视频均通过 20 个均匀采样帧检查，并使用一个成功 2k episode 作为视觉目标物参考。下表“观察到”仅描述可见行为，“可能解释”只是推测。本实验没有记录内部 attention、预测 language token、contact force 或 object-ID log，因此无法直接观察模型意图和根因。

## 案例

| Checkpoint / episode | 协议结果 | 观察到的行为 | 分类 | 可能解释，尚未证明 |
| --- | --- | --- | --- | --- |
| 1k / episode 4，seed label 1004，fixed state 4 | 520 steps 后 horizon 耗尽 | Gripper 反复接近并接触蓝色目标罐，但没有持续抓起并运入篮子；第二个目标未完成。 | 抓取建立失败 / 局部反复重试 | 该存储机器人—物体几何下的抓取位姿或 gripper timing 可能较临界；chunked action 可能反复回到相似的无效接近。 |
| 2k / episode 14，seed label 1014，fixed state 14 | 520 steps 后 horizon 耗尽 | Policy 抓起作为干扰物的牛奶盒并放入篮子；之后与目标颜色的罐子交互，但没有完成两个指定放置。 | 错误物体选择；恢复不完整 | Visual-language grounding 可能混淆干扰物与指定目标，或者早期错误动作把杂物移动到 policy 恢复分布之外。 |
| 2k / episode 18，seed label 1018，fixed state 18 | 520 steps 后 horizon 耗尽 | 机械臂推倒多个包装，之后把一个非目标小盒子运进篮子，最终未放入两个目标物。 | 错误物体选择 + 杂物碰撞 | 该布局下目标识别可能不稳定；碰撞可能进一步改变场景并增加恢复难度。 |

两个 2k 失败具有可见的错误物体选择共同模式。1k 失败不同：它保持在目标附近，但无法抓取并搬运。因为只有三个失败案例，这只是案例清单，不是总体失败频率估计。

## 视觉产物

- 1k episode 4 视频：`../pi05_checkpoint_001000/videos/eval_episode_4.mp4`
- 1k episode 4 contact sheet：`failure_contact_sheets/pi05_checkpoint_001000_eval_episode_4_contact_sheet.jpg`
- 2k episode 14 视频：`../pi05_checkpoint_002000_30ep/videos/eval_episode_14.mp4`
- 2k episode 14 contact sheet：`failure_contact_sheets/pi05_checkpoint_002000_30ep_eval_episode_14_contact_sheet.jpg`
- 2k episode 18 视频：`../pi05_checkpoint_002000_30ep/videos/eval_episode_18.mp4`
- 2k episode 18 contact sheet：`failure_contact_sheets/pi05_checkpoint_002000_30ep_eval_episode_18_contact_sheet.jpg`
- 成功 2k episode 0 参考：`success_reference/pi05_checkpoint_002000_30ep_eval_episode_0_contact_sheet.jpg`
