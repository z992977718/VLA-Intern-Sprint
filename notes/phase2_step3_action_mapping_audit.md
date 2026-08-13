# Phase 2 / Step 3 Action Mapping 审计

## Pi0.5 输出的真实语义

checkpoint 的真实输出 feature 是 `action: shape=[7]`，`chunk_size=50`。后处理器使用 checkpoint 自带的 MEAN_STD unnormalizer。LIBERO 当前使用相对 `OSC_POSE` 控制：

| 维度 | 语义 | 当前 robosuite 默认缩放 |
| --- | --- | --- |
| 0–2 | 归一化 EEF position delta；缩放后加到 controller 当前 EEF position | `[-1,1] → [-0.05,0.05]` 米/控制步 |
| 3–5 | 归一化 EEF axis-angle orientation delta；相对当前 EEF orientation 更新目标 | `[-1,1] → [-0.5,0.5]` 弧度/控制步 |
| 6 | Panda gripper command | `-1=open`，`+1=closed` |

位置使用 robosuite 仿真中的当前 EEF/world Cartesian position；方向增量与当前 EEF orientation 组合更新目标。它不是七个关节角，也不能在未对齐 Isaac 坐标域时直接复用。

## Isaac 当前控制接口

Step 1 的 `/joint_command` 是 `sensor_msgs/JointState`，字段 `name` 为 `panda_joint1..7`，`position` 是七个 arm joint 的绝对位置目标。Isaac ArticulationController 读取 `positionCommand`。

```text
Pi0.5: [Δx, Δy, Δz, Δrx, Δry, Δrz, gripper]
Isaac: [q1, q2, q3, q4, q5, q6, q7]
```

因此：`Pi0.5 Action ≠ 当前 /joint_command`，判定为 **MISMATCH**，不能直接执行。

## Step 4 需要解决但本阶段未实现

- 坐标系和控制周期对齐；
- OSC/IK 或其他经过验证的 EEF-to-joint 转换；
- position/orientation delta 的缩放与限幅；
- gripper 命令到 Isaac 两指关节的映射；
- Action Chunk 执行策略、刷新频率、安全层和停止条件。

本阶段没有创建 VLA action publisher，没有调用控制器，也没有让 Franka 执行任何预测动作。
