# Phase 2 / Step 1 初学者学习笔记

本阶段只建立了“ROS 2 关节命令 → Isaac Sim Franka → ROS 2 关节反馈”的最小闭环，没有接入相机、VLA、MoveIt 或抓取任务。

## 1. Isaac Sim 是什么？

- 专业解释：NVIDIA 的机器人仿真平台，使用 USD 描述场景，并通过 PhysX、RTX 渲染和机器人扩展运行物理仿真。
- 小白解释：它是一台运行在 GPU 上的“虚拟机器人实验室”。
- 本项目位置：远程 RTX 6000D 上的 Isaac Sim 6.0.1 负责加载 Franka、运行物理并执行关节命令。

## 2. USD 是什么？

- 专业解释：Universal Scene Description 是描述场景层级、几何、材质、关节和引用关系的格式与组合系统。
- 小白解释：它像一个能装下机器人零件、摆放位置和连接关系的三维场景文件。
- 本项目位置：官方 `franka.usd` 被加载到 Stage 的 `/panda` prim。

## 3. Franka Panda 是什么？

- 专业解释：Franka Panda 是 7 自由度协作机械臂；本项目使用 NVIDIA 提供的仿真资产。
- 小白解释：它是一只由 7 个主要旋转关节组成的机械手臂。
- 本项目位置：官方资产路径为 `Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd`。

## 4. link 是什么？

- 专业解释：link 是机器人运动学树中的刚体部件，关节把不同 link 连接起来。
- 小白解释：link 就像人的上臂、前臂等硬质骨段。
- 本项目位置：Franka 的臂段和末端部件是多个 link。

## 5. joint 是什么？

- 专业解释：joint 约束两个 link 之间允许的相对运动，并具有位置、速度和力矩状态。
- 小白解释：joint 就像肘关节，决定相邻部件怎样转动。
- 本项目位置：smoke test 控制 `panda_joint1` 到 `panda_joint7`。

## 6. DoF 是什么？

- 专业解释：自由度（Degree of Freedom）表示系统可独立控制的运动变量数量。
- 小白解释：一个自由度就是一个可以独立变化的动作方向。
- 本项目位置：Franka 手臂有 7 个主要旋转自由度；手指关节不在本次命令中。

## 7. articulation 是什么？

- 专业解释：articulation 是由 link 和 joint 组成、由物理引擎统一求解的多刚体关节树。
- 小白解释：它是“整只机械臂”，而不是互不相关的零件集合。
- 本项目位置：Stage 中 `/panda` 是本次控制器的 articulation 路径。

## 8. Articulation Controller 是什么？

- 专业解释：Isaac Sim OmniGraph 节点，把关节名与位置、速度或力矩命令施加给目标 articulation。
- 小白解释：它是把 ROS 命令真正交给虚拟机械臂执行的“驱动器”。
- 本项目位置：订阅节点的 position command 连接到 `IsaacArticulationController`。

## 9. `/joint_states` 是什么？

- 专业解释：ROS 2 标准 `sensor_msgs/msg/JointState` 状态话题，携带关节名、位置、速度和力矩。
- 小白解释：机器人用它汇报“我现在每个关节在哪里”。
- 本项目位置：Isaac Sim 发布 7 个手臂关节和 2 个手指关节的仿真状态。

## 10. `/joint_command` 是什么？

- 专业解释：本 Action Graph 配置的 `JointState` 命令话题，位置字段被送入 articulation controller。
- 小白解释：控制程序用它告诉机械臂“请转到这些角度”。
- 本项目位置：项目节点向它发布 7 个目标关节位置。

## 11. ROS 2 Bridge 是什么？

- 专业解释：Isaac Sim 扩展，在 ROS 2 DDS 图与 OmniGraph/仿真数据之间转换消息。
- 小白解释：它是 ROS 2 和仿真世界之间的翻译员。
- 本项目位置：`isaacsim.ros2.bridge` 连接两个标准 JointState 话题和仿真节点。

## 12. Publisher / Subscriber 分别是谁？

- 专业解释：ROS 2 节点对某话题发布消息，订阅者注册回调接收消息；同一系统可同时承担两种角色。
- 小白解释：Publisher 是“说话的人”，Subscriber 是“听话的人”。
- 本项目位置：测试节点发布 `/joint_command`、订阅 `/joint_states`；Isaac Sim 的方向正好相反。

## 13. position control 是什么？

- 专业解释：控制目标是期望关节位置，底层驱动和物理求解器使实际位置靠近目标。
- 小白解释：我们指定“转到多少度”，而不是直接指定电机力矩。
- 本项目位置：目标位置到达判据是最大绝对误差小于 `0.08 rad`，最终一键复现实测为 `0.0560 rad`。

## 14. 为什么机械臂不能直接接受“拿杯子”？

- 专业解释：低层控制器需要数值化关节或末端执行器目标；自然语言还缺少目标识别、规划和动作生成环节。
- 小白解释：“拿杯子”是意图，不是电机能直接执行的数字。
- 本项目位置：本阶段只发送 7 个关节角度，不处理语言或物体。

## 15. 为什么这一阶段不需要 VLA？

- 专业解释：在接入高层策略前，应先独立验证仿真、ROS 2 通信、控制器与反馈链路，缩小故障范围。
- 小白解释：先确认“神经和肌肉”能工作，再接“大脑”。
- 本项目位置：闭环由固定 JointState 目标完成，Pi0.5 没有加载。

## 16. 未来 Pi0.5 会插在哪里？

- 专业解释：未来策略位于 observation adapter 之后、action adapter 之前；它依据观测生成动作，再映射到仿真控制接口。
- 小白解释：Pi0.5 将替代当前写死的目标数组，决定下一步动作。
- 本项目位置：将来会在 ROS 2 命令发布节点上游，但这属于 Step 2，当前尚未实现。
