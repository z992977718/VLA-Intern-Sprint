# Phase 2 / Step 3 学习笔记

## 1. Policy Input Adapter 是什么

- **专业解释：** 把上游传感器/中间件的数据结构转换成 policy processor 约定的 feature schema，同时保留单位、坐标系、时间和语义证据。
- **小白理解：** 像一个“翻译器”，把 ROS 2 说的话翻译成 Pi0.5 能读懂的格式。
- **本项目作用：** 把两张图、Franka 状态和一句语言组织成 `observation.images.image/image2`、`observation.state` 和 `task`。

## 2. 为什么 joint_states 不能直接给 Pi0.5

- **专业解释：** Isaac 是 7 个 arm joint 加 2 个 finger joint 的 9D joint-space 表示；Phase 1 checkpoint 需要 8D task-space state。
- **小白理解：** 一个描述“每个关节弯了多少”，另一个描述“手在哪里、朝哪里、夹爪多开”，不是同一种数据。
- **本项目作用：** 先得到末端位姿，再按 Phase 1 顺序构造 8D。

## 3. EEF 是什么

- **专业解释：** End Effector，机械臂运动学链末端用于操作环境的坐标框架。
- **小白理解：** 可以把它理解成机械臂的“手”。
- **本项目作用：** 使用 Isaac `/panda/panda_hand` 的世界位姿作为当前 EEF 样本。

## 4. FK 是什么，为什么这里需要 FK

- **专业解释：** Forward Kinematics 根据关节构型计算末端位姿。
- **小白理解：** 已知每个关节弯多少，算出手在哪里、朝哪边。
- **本项目作用：** 直接读取 Isaac 物理场景对当前 articulation 求得的 `panda_hand` local-to-world transform，没有手写一套易错的 FK。

## 5. position 和 orientation 是什么

- **专业解释：** position 是参考坐标系中的三维平移；orientation 是三维旋转。
- **小白理解：** 前者回答“手在哪里”，后者回答“手朝哪里”。
- **本项目作用：** position 用米，orientation 从四元数转成 axis-angle。

## 6. axis-angle 是什么

- **专业解释：** 用旋转轴乘旋转角得到三维旋转向量。
- **小白理解：** “绕哪个方向转、转多少”压缩成三个数。
- **本项目作用：** 由 LeRobot 官方 LIBERO processor 计算 state 第 3–5 维。

## 7. processor 为什么重要

- **专业解释：** processor 固化 key rename、batch、归一化、状态提示、tokenization、device 和后处理规则。
- **小白理解：** 模型不仅在意数据内容，也在意格式和尺度；少一步就可能完全读错。
- **本项目作用：** 复用 checkpoint 自带 processor 和 LeRobot `LiberoProcessorStep`，没有另写“差不多”的归一化。

## 8. inference 和 training 的区别

- **专业解释：** inference 只前向生成输出；training 还计算 loss、backward 并更新参数。
- **小白理解：** inference 是“答题”，training 是“学习后改脑子”。
- **本项目作用：** 只执行 `torch.inference_mode()`，没有 optimizer、backward 或梯度更新。

## 9. predict_action_chunk 是什么

- **专业解释：** Pi0.5 根据当前 observation 通过迭代生成一次预测一段动作序列。
- **小白理解：** 模型不是只给下一步，而是一次计划接下来很多小步。
- **本项目作用：** 对同一静止观测真实调用 3 次，而不是从缓存 action queue 取值冒充推理。

## 10. 为什么一次输出很多 Action

- **专业解释：** chunked policy 可以减少模型调用频率，并在一段短时域内表达连续行为。
- **小白理解：** 像一次写出接下来 50 个动作草稿，而不是每走一步重新想一次。
- **本项目作用：** checkpoint 的 `chunk_size=50`，真实输出 50×7。

## 11. Action Chunk 是什么

- **专业解释：** 具有时间维的 action tensor，当前 shape 为 `[batch, horizon, action_dim]`。
- **小白理解：** 一串按时间排序的动作。
- **本项目作用：** 单次输出 `[1,50,7]`，但本阶段一项也没有执行。

## 12. 为什么现在不能直接控制 Franka

- **专业解释：** policy action 和 controller command 在控制空间、坐标系、缩放、单位及 gripper 表示上不一致。
- **小白理解：** 模型说“手向左一点”，控制器却等着“7 个关节各到多少度”。
- **本项目作用：** 明确判定 MISMATCH，因此停在 Action Chunk 观察。

## 13. Pi0.5 的 7D Action 和 Franka 7 个关节为何不是一回事

- **专业解释：** Pi0.5 的前六维是笛卡尔 EEF pose delta，第七维是 gripper；Franka 7 关节位置是 joint-space 向量。
- **小白理解：** 两边碰巧都是 7 个数，但每个数的含义不同。
- **本项目作用：** 禁止按维度相等直接 reshape 或发布。

## 14. Action Adapter 下一阶段要解决什么

- **专业解释：** 要完成坐标变换、控制空间转换、缩放、时序、gripper 映射、限幅和安全验证。
- **小白理解：** 需要一个可靠的“动作翻译器”和“安全检查员”。
- **本项目作用：** 这是 Step 4 的输入；本阶段未开发和执行。

## 15. Step 3 在 VLA 闭环中的位置

- **专业解释：** 已验证 perception/state/language → policy → action proposal；尚未验证 action adaptation → controller → new observation。
- **小白理解：** 现在模型已经“看见并提出动作”，但还没有让机器人真正动。
- **本项目作用：** 证明前半条数据链可运行，同时把控制边界留给后续独立验收。
