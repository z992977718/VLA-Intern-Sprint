# Phase 3 / Step 7B: LIBERO 8D State 语义审计

本记录只描述实际源码和 2026-08-13 的静态采样，不代表新训练、Pi0.5 推理或任务 rollout。

## 到 Pi0.5 的真实数据链

```text
MuJoCo / robosuite raw observation
  -> robot0_eef_pos
  -> robot0_eef_quat (xyzw)
  -> robot0_gripper_qpos
  -> LiberoEnv._format_raw_obs
  -> LiberoProcessorStep._quat2axisangle
  -> observation.state
     [eef_x, eef_y, eef_z, axisangle_x, axisangle_y, axisangle_z, gripper_0, gripper_1]
```

LeRobot 侧的实际 processor 是 `LiberoProcessorStep`。它读取的姿态是原始观测的 `robot0_eef_quat`，四元数顺序为 `xyzw`，并以第四个分量作为 `w` 转为 axis-angle。因此，`robots[0].controller.ee_ori_mat` 可用于控制器参考系诊断，但不是当前 Pi0.5 8D state 的直接姿态输入。

## 静态采样事实

五组明确给定的 Panda 7D 关节角独立写入 LIBERO。每组读取：

- `robot0_eef_pos`：原始 EEF 位置观测，单位米；
- `robot0_eef_quat`：原始 EEF 姿态观测，`xyzw`；
- `robot0_gripper_qpos`：两个手指 qpos。

在本任务环境里，夹爪数值为：open `[0.04, -0.04]`，intermediate `[0.02, -0.02]`，closed `[0.0, 0.0]`。这说明两个分量具有镜像符号约定；不能只因都是两个 finger qpos 就把别的仿真器数值原样视为等价。

原始采样：`results/phase3_step7/state_mapping_audit/libero_state_semantics.json`。
