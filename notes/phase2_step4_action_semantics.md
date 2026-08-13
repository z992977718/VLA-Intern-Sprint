# Phase 2 / Step 4 动作真实语义

## 结论

`predict_action_chunk()` 先输出模型归一化空间中的张量；Step 4 调用了 checkpoint 自带的 `policy_postprocessor.json`，其中 `unnormalizer_processor` 使用训练数据的 `MEAN_STD` 统计。因此，保存和执行的 7 维数值已经是 **LIBERO 环境控制输入**，不再是模型归一化张量，但也不是直接以米、弧度表达的物理量。

## 7 维含义与缩放

当前实际安装的 robosuite 1.4.0 `controllers/config/osc_pose.json` 和 `controllers/base_controller.py::scale_action` 确认：

| 维度 | 环境输入语义 | robosuite 物理缩放 |
| --- | --- | --- |
| 0–2 | 无量纲 EEF 平移控制输入 | 先裁剪到 `[-1,1]`，再映射到 `[-0.05,0.05]` m |
| 3–5 | 无量纲 EEF 轴角增量控制输入 | 先裁剪到 `[-1,1]`，再映射到 `[-0.5,0.5]` rad |
| 6 | Panda gripper command | `-1=open`，`+1=closed`；实际 gripper model 依据符号逐步更新内部双指命令 |

`control_delta=true`。平移目标由 `current_position + scaled_delta` 得到，是 robosuite world/site Cartesian 坐标中的增量。

姿态不是轴角相加。实际 `set_goal_orientation()` 执行：

```text
R_delta = axis_angle_to_rotation_matrix(scaled_delta[3:6])
R_target = R_delta @ R_current
```

这是左乘的 spatial/world-frame 增量。Step 4 在 Isaac `/World` 中通过 ±x/±y/±z 的小幅真实运动验证了轴方向一致性。

## 数据与 checkpoint 证据

- dataset：40 tasks、273,465 frames、10 Hz、action shape `[7]`。
- action 全数据范围：前三维约 `[-0.9375,0.9375]`，旋转三维约 `[-0.375,0.375]`，gripper `[-1,1]`。
- checkpoint 后处理统计和 robosuite 源码快照保存在 `results/phase2_step4/source_audit/`。
- 本次首动作是在 checkpoint 反归一化之后得到；其中 gripper 为 `1.0194`，说明模型输出可轻微超过控制器输入范围，robosuite 本身也会先 clip。Step 4 safety layer 施加了更保守的 smoke-test 限幅。
