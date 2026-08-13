# Phase 2 / Step 2：Isaac Franka 与 LIBERO State Mapping 审计

## Isaac `/joint_states` 实测

Step 1 的真实 `sensor_msgs/JointState` 消息按当次发布顺序包含 9 个名字：

1. `panda_joint1`
2. `panda_joint2`
3. `panda_joint3`
4. `panda_joint4`
5. `panda_joint5`
6. `panda_joint6`
7. `panda_joint7`
8. `panda_finger_joint1`
9. `panda_finger_joint2`

`position`、`velocity`、`effort` 当次都为 9 维。数组顺序不能被假设为永久固定；项目的 `observation_adapter_node` 使用 `dict(zip(msg.name, values))` 的等价显式逻辑，为每种数值建立 `joint_name → value` 映射，并同时保存 `raw_order`。

## 维度与语义比较

| 比较项 | Phase 1 LIBERO `observation.state` | Phase 2 Isaac `/joint_states` | 结论 |
| --- | --- | --- | --- |
| 原始维度 | 8 | 9 positions + 9 velocities + 9 efforts | 不同 |
| 机械臂表示 | 末端位置 3 + axis-angle 3 | 7 个 revolute joint 的角度/速度/力矩 | 不同 |
| gripper | 两个 gripper qpos | 两个 finger joint position/velocity/effort | 数量相同但量纲、零点、范围和正负约定未校准 |
| 顺序 | 固定为 eef pos、eef axis-angle、gripper qpos | 消息携带 name，不能依赖数组位置 | 不同 |
| 可直接输入 Pi0.5 | 是，且会按 Phase 1 stats 归一化 | 否 | `MISMATCH` |

## 当前映射状态

- 已实现：ROS JointState 的 joint-name 显式映射与原始维度记录。
- 未实现：Forward Kinematics、坐标系变换、quaternion→axis-angle、夹爪范围/符号校准。
- 未实现的原因：这些会改变状态语义，属于 Step 3 前必须单独设计和验证的适配，不应为了“凑 8 维”偷偷处理。
- 即使把 `7 arm joints + 1 gripper summary` 拼成 8 维，它仍不等于 LIBERO 的 `eef pos(3) + axis-angle(3) + gripper qpos(2)`。

## Step 3 前置问题

1. 明确 Franka base、hand、camera 与 policy 所用坐标系。
2. 用经过验证的机器人模型计算末端笛卡尔 pose，而不是截取 joint 数组。
3. 确认 quaternion 顺序和 axis-angle 约定。
4. 校准两个 Isaac finger joint 到 LIBERO gripper qpos 的数值范围与方向。
5. 确认能否沿用 Phase 1 数据统计；域和语义改变时不能盲目使用旧 normalization stats。
