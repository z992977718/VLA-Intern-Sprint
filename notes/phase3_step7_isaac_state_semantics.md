# Phase 3 / Step 7B: Isaac 当前 8D State Adapter 语义审计

本记录描述现有项目代码，没有修改 State Adapter。

## 当前构造链

```text
/joint_states
+ /World/panda/panda_hand 的 USD world pose
+ EEF_OFFSET_IN_HAND_M = [0, 0, 0.0951034858] m
-> tool_position = hand_position + R_hand @ offset_local
+ panda_hand quaternion (wxyz -> xyzw)
+ panda_finger_joint1 / panda_finger_joint2 qpos
-> LiberoProcessorStep
-> [x, y, z, rx, ry, rz, f1, f2]
```

位置使用的是 `panda_hand` 加局部工具偏移后的 tool point；姿态仍直接使用 `panda_hand` 的姿态。偏移是 `R_hand @ offset_local`，会随手部朝向旋转，不是固定世界坐标偏移。五姿态计算中该公式残差为数值零，因此没有发现“world-fixed offset”实现错误。

Isaac 四元数源是 USD 的 `wxyz`，在进入 LeRobot processor 前显式改为 `xyzw`。夹爪关节名为 `panda_finger_joint1`、`panda_finger_joint2`，本次静态采样中 open 为约 `[0.04, 0.04]`，closed 为约 `[0, 0]`。

因此，夹爪开合趋势一致，但与 LIBERO 的镜像符号 qpos 不是数值等价输入。原始采样：`results/phase3_step7/state_mapping_audit/isaac_state_semantics.json`。
