# 失败分析

## 证据边界

通过完整视频和均匀采样的 contact sheet 检查两个新增 horizon failure。“观察到”只限于可见环境行为。“可能解释”仍是假设；本实验没有记录 policy attention、language token、object ID、预测目标或 contact-force trace。

## 新增评测初态中的失败

| Initial state / episode | 观察到的失败 | 分类 | 可能解释，尚未证明 |
| --- | --- | --- | --- |
| 41 / episode 11 | Policy 与目标区域交互，随后把一个非目标小盒子运进篮子。之后还移动了一个目标罐，但在 520 steps 前未放入两个要求目标。 | 错误物体选择；杂物位移；horizon 耗尽 | 在该存储布局中目标 grounding 可能不稳定，错误放置也可能让场景偏离熟悉的恢复轨迹。 |
| 49 / episode 19 | 机械臂推动多个包装，抓取牛奶盒并将该干扰物放入篮子；之后接近另一物体，但未在 520 steps 前完成两个目标。 | 错误物体选择；杂物碰撞；horizon 耗尽 | 视觉目标选择可能混淆干扰物与指令目标，早期碰撞也可能增加后续恢复难度。 |

产物：

- state 41 视频：`heldout_initial_states/videos/eval_episode_11.mp4`
- state 41 contact sheet：`failure_contact_sheets/heldout_initial_states_eval_episode_11_contact_sheet.jpg`
- state 49 视频：`heldout_initial_states/videos/eval_episode_19.mp4`
- state 49 contact sheet：`failure_contact_sheets/heldout_initial_states_eval_episode_19_contact_sheet.jpg`

## 全部 50 个固定状态中的模式

此前 2k 运行在 state 14 和 18 失败，视频同样能看到错误物体放置或选择。新增失败 state 41 和 49 重复了这一可观察模式。因此，50 个固定状态中的四个 2k 失败都涉及错误物体选择。

这一证据支持对四个案例作具体的失败模式陈述；它不能证明 VLM 误解了语言，不能把根因定位到某个内部模块，也不能估计该失败模式在当前任务与固定状态集合之外的频率。

Cross-task 实验在 training-exposure audit 后被正确跳过，因此不存在 cross-task 视频。
