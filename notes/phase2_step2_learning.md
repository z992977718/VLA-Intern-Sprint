# Phase 2 / Step 2 学习笔记

## 1. Camera 为什么也是 Observation？

- **专业解释：** Camera 提供环境的视觉测量，VLA 用它识别物体、空间关系和机器人与场景的相对状态。
- **小白解释：** 机械臂的相机相当于“眼睛”；只知道关节弯了多少，不知道桌上是什么。
- **本项目位置：** external 与 wrist tracking 两路 256×256 RGB 已真实发布并保存。第二路是虚拟跟随视角，不是已标定实体 eye-in-hand 相机。

## 2. `sensor_msgs/Image` 是什么？

- **专业解释：** ROS 2 的原始图像消息，包含时间戳、frame_id、宽高、encoding、每行步长和像素字节。
- **小白解释：** 它不只是图片，还带“什么时候拍、哪个相机拍、像素怎么排列”。
- **本项目位置：** Adapter 订阅两个 Image topic，检查这些字段并把 RGB 字节写成 PNG。

## 3. `robot_state` 和 `/joint_states` 有什么区别？

- **专业解释：** `robot_state` 是 policy 约定的特征；`/joint_states` 是 ROS 的通用关节测量消息。两者维度、坐标和语义不必相同。
- **小白解释：** 一个是“模型想看的摘要”，另一个是“机器人报出的关节清单”。
- **本项目位置：** Phase 1 state 是末端 pose+夹爪 8 维；Isaac 消息是 9 个命名关节。

## 4. 为什么不能直接把 `/joint_states` 数组塞进 Pi0.5？

- **专业解释：** Pi0.5 checkpoint 使用特定 feature schema 与统计量；错误顺序或物理语义会使归一化和预测失效。
- **小白解释：** 模型问的是“手在哪里”，你却回答“每个关节转了多少”，数字再多也答非所问。
- **本项目位置：** Step 2 只保存 name→value，不强行转换。

## 5. 为什么同样是 7 维也可能不是一种 Action？

- **专业解释：** 向量长度不定义控制空间；LIBERO 7 维是末端笛卡尔增量+gripper，Step 1 的 7 维是 Franka joint position target。
- **小白解释：** 七个数字可能是七个关节，也可能是“移动3维+旋转3维+夹爪1维”。
- **本项目位置：** Action compatibility 为 MISMATCH，本阶段没有发送 VLA action。

## 6. Observation Adapter 是什么？

- **专业解释：** 它把异步 ROS sensor messages 整理成明确、可检查的统一数据结构，但不改变未经验证的物理语义。
- **小白解释：** 像一个装订员，把同一时刻附近的图片、关节状态和任务说明装进一份档案。
- **本项目位置：** `observation_adapter_node.py`；不包含 policy 或控制代码。

## 7. 为什么需要时间同步？

- **专业解释：** 图像和 proprioception 若相差过大，policy 会基于互相矛盾的时刻决策。
- **小白解释：** 不能拿“一秒前的照片”配“现在的手臂位置”。
- **本项目位置：** Adapter 记录两个 header timestamp 与绝对时间差，当前不实现硬实时同步。

## 8. Camera frame / frame_id 是什么？

- **专业解释：** frame 描述传感器坐标系，frame_id 标识消息数据属于哪个坐标系；外参变换依赖这一标识。
- **小白解释：** 它告诉系统“这张照片是从哪只眼睛的方向看出去的”。
- **本项目位置：** 已发布 `external_camera_frame` 与 `wrist_camera_frame`；后者当前表示虚拟 tracking camera frame。

## 9. RGB 为什么还需要 resize/normalize？

- **专业解释：** 模型要求固定空间尺寸和数值范围；Pi0.5 把输入 resize-with-pad 到 224×224，并映射到 `[-1,1]`。
- **小白解释：** 不同相机照片大小不同，先统一成模型熟悉的“纸张大小和亮度刻度”。
- **本项目位置：** Phase 2 保存原始 ROS RGB；真正 resize/normalize 要到后续 policy processor，不在 Adapter 偷做。

## 10. VLA 为什么需要语言？

- **专业解释：** 同一视觉状态可能对应不同目标，语言提供任务条件。
- **小白解释：** 看到桌上多个物体后，还要知道“要拿哪一个”。
- **本项目位置：** Step 2 使用固定 `move the robot arm`，只验证字段结构，不执行语义任务。

## 11. Observation 和 State 有什么区别？

- **专业解释：** State 通常指系统内部状态；Observation 是传感器可得到、供 agent 使用的测量，可能不完整并带噪声。
- **小白解释：** “世界真实是什么样”是 state，“机器人实际看见和测到什么”是 observation。
- **本项目位置：** 图片、关节测量、语言共同组成机器人侧 Observation；其中 robot_state 只是一个子字段。

## 12. 当前 Observation 下一步如何进入 Pi0.5？

- **专业解释：** Vulkan Camera 已解决；下一步仍需解决末端 pose/夹爪状态语义、坐标系和 normalization 兼容，再由 LeRobot processor 转换 feature keys、图像和语言 token。
- **小白解释：** 先让眼睛真的看见，再把“关节清单”翻译成模型熟悉的“手的位置”，最后才可以问模型下一步怎么动。
- **本项目位置：** 这些属于 Step 3 的前置条件；本轮明确停止，不运行 inference。
