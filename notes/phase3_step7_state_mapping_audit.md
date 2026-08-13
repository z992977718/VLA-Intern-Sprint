# Phase 3 / Step 7B: State Mapping / EEF Calibration Audit

## 范围

同一组明确的 Panda 7D 关节向量分别写入 LIBERO 和 Isaac，共五个姿态。没有调用 Pi0.5、没有训练、没有 task rollout、没有重跑 Step 6，也没有修改上游或 State Adapter。

## 量化结果

- 当前 Isaac tool point 到 LIBERO `robot0_eef_pos`：平均 `37.870 mm`，最大 `70.814 mm`，最小 `2.517 mm`。
- 即使用一个仅用于诊断的自由刚体配准，残差仍为平均 `37.142 mm`、最大 `63.719 mm`。因此不能以固定外参直接宣称位置已经对齐。
- Pi0.5 实际姿态源 `robot0_eef_quat` 与 Isaac `panda_hand`：平均 `0.434 rad`，最大 `0.862 rad`，最小 `0.025 rad`。单一固定旋转没有显著降低五姿态误差，不能据此实施固定姿态修正。
- `controller.ee_ori_mat` 与 policy-source quaternion 差约 `1.571 rad`，是单独的控制器 frame 约定，不能与 Pi0.5 state 输入混淆。
- 95.1035 mm 偏移正确随 `R_hand` 旋转，不存在已确认的世界固定偏移 bug。
- 夹爪的 open/intermediate/closed 语义趋势一致，但 LIBERO 镜像符号与 Isaac 同号 finger qpos 不是数值等价。
- 时间同步单独记录：此前 RTX 5090 migration smoke 的 image-to-joint 最大 skew 为 `0.15 s`，状态为 `POTENTIAL ISSUE`；本阶段未修改同步策略。

## 分类

| 项目 | 结论 |
| --- | --- |
| Position semantics | MISMATCH |
| Orientation semantics | APPROXIMATE |
| Tool-point calibration | APPROXIMATE |
| Gripper state | MISMATCH |
| Time synchronization | POTENTIAL ISSUE |
| Overall State Mapping | MISMATCH |

## 解释边界

这些证据说明 Step 6 使用的 observation state 可能不等价于 LIBERO policy 所见 state，并可能参与解释 0/3；但不能证明这是唯一原因，也不能归因到 Pi0.5、VLM、attention 或视觉模块内部。

保留 `results/phase3_step7/state_mapping_audit/` 作为 BEFORE-FIX 证据。建议的唯一下一步是 **A. Fix State Mapping and rerun calibration**，但当前不执行修复，等待明确授权。
