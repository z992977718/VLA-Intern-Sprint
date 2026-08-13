# Phase 2 / Step 3 Robot State Adapter

## 结论

转换链在结构和数值层面已通过真实运行，但跨仿真器语义只能判定为 **PARTIAL**，不能称为完整 MATCH。

```text
/joint_states（7 arm + 2 finger）
→ 按 joint name 校验顺序
→ Isaac panda_hand 的 /World 变换（真实运动学结果）
→ EEF xyz（米）+ quaternion xyzw
→ LeRobot LiberoProcessorStep
→ EEF axis-angle（弧度）
→ 拼接两维 finger qpos
→ observation.state，shape=[1,8]
```

## 映射审计

| Isaac 来源 | 转换 | Pi0.5 目标 | 判定 |
| --- | --- | --- | --- |
| `/joint_states` 中 `panda_joint1..7` | 用名称校验，不直接送入 Pi0.5 | 用来确定当前 Franka 构型 | MATCH |
| `/panda/panda_hand` 的 USD local-to-world transform | 读取 `/World` 下平移 | state 0–2：EEF xyz | PARTIAL |
| Isaac 右手四元数 `wxyz` | 归一化并显式重排为 `xyzw` | LIBERO processor 输入 quaternion | MATCH（表示层） |
| `xyzw` quaternion | LeRobot `_quat2axisangle`：`angle=2*acos(w)`，`axis=xyz/sqrt(1-w²)` | state 3–5：axis-angle | MATCH（算法层） |
| `panda_finger_joint1/2` position | 保留命名顺序与真实值 | state 6–7：gripper qpos | PARTIAL |

PARTIAL 的原因：Isaac `/World` 与 LIBERO/robosuite 的末端控制参考域没有完成跨仿真器外参/零点标定；两套 Panda finger joint position 虽然都是两维位置，但量程、零点和符号等价性尚未证明。当前 robosuite Panda 源码的默认 gripper qpos 为 `[0.020833, -0.020833]`，而本次 Isaac 样本为 `[0.0, 0.0]`，不能按维度相同直接视为同一 convention。

EEF 变换文件与 ROS 图像/关节快照没有 message-level 同步。本次 Franka 全程保持静止，因此它们可作为同一静止观测样本；移动场景仍需建立同步机制。

## 真实数值样本

```text
arm joints rad = [0.0120, -0.5686, 0.0, -2.8109, 0.0, 3.0368, 0.7410]
EEF xyz m      = [0.39052784, 0.00468519, 0.46012837]
quat wxyz      = [0.00630024, 0.92095954, 0.02598396, 0.38873986]
quat xyzw      = [0.92095953, 0.02598396, 0.38873985, 0.00630024]
axis-angle rad = [2.88173223, 0.08130522, 1.21638811]
finger qpos    = [0.0, 0.0]
state 8D       = [0.39052784, 0.00468519, 0.46012837,
                  2.88173223, 0.08130522, 1.21638811,
                  0.0, 0.0]
```

完整机器可读证据见 `results/phase2_step3/robot_state_sample.json` 和 `eef_pose.json`。
