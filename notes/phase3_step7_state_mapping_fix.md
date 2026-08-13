# Phase 3 / Step 7B.1：状态映射修复与复核

本轮只修复已由 Step 7B 证明的问题，并对原五个姿态和五个独立 hold-out 姿态做静态复核。没有调用 Pi0.5，没有训练、任务 rollout 或 Step 6 重跑。

## 修复结果

- 位置：原适配器使用 `p_hand + R_hand @ [0, 0, 0.0951034858]`。现在的候选位置源是 Isaac 资产中真实存在的 `/World/Robot/panda_hand/tool_center`。它是 `panda_hand` 的刚性子 frame，不是人为加入世界坐标常数偏移。
- 夹爪：适配器将 Isaac 物理关节 `[finger1, finger2]` 转为 LIBERO-compatible `[finger1, -finger2]`，再交给 `LiberoProcessorStep`。
- 姿态：未加入固定补偿旋转。证据不足以从 frame semantics 推导可靠转换，因此保持 `UNRESOLVED`。
- 时间同步：最大 image-to-joint skew 仍为 `0.15 s`，本轮未改。

## 位置误差（真实静态采样）

| 集合 | 修复前平均 / 最大 | tool_center 平均 / 最大 |
|---|---:|---:|
| 原五姿态 calibration | 37.870 / 70.814 mm | 7.874 / 8.207 mm |
| 五个独立 hold-out 姿态 | 62.852 / 79.705 mm | 7.800 / 7.898 mm |

位置在两组姿态上均显著改善，但仍有约 8 mm 残差，因此分类为 `APPROXIMATE`，不是 `MATCH`。

## 范围与结论

修改仅涉及 `phase3/scripts/state_mapping_adapter.py` 和 `phase2/scripts/policy_input_adapter.py`。没有改 Action Adapter、PINK、Safety、Camera、Pi0.5、LIBERO 上游、Controller、Scene、Task，也没有改冻结的 Step 6 脚本和结果。

旧 State Mapping 可能影响 Step 6 的 0/3，但不能证明它是唯一原因。此时不应重跑 Step 6。下一诊断阶段应是 Scripted Grasp Oracle，而不是直接声称任务迁移已修复。

证据文件：`results/phase3_step7/state_mapping_fix/`。
