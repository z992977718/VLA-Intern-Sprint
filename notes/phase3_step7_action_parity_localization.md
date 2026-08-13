# Phase 3 / Step 7A.1：Action Parity Mismatch 定位

## 执行边界

本阶段只读取 Step 7A 已完成的 JSON 结果，未调用 Pi0.5，未训练，未运行 Isaac/LIBERO 仿真，未重跑 Step 6 或 Step 7A。完整历史输入使用 `results/phase3_step7/action_parity_attempt2/`；早期 `action_parity/` 是不完整尝试，不能作为完整证据。

## 关键总表

| Action | LIBERO commanded target | Isaac commanded target | LIBERO actual delta | Isaac actual delta | direction cosine | magnitude ratio | status |
|---|---|---|---|---|---:|---:|---|
| +X | +5.028 mm X | +5.000 mm X | 0.876 mm | 1.425 mm | 0.871 | 1.627 | APPROXIMATE |
| -X | -4.972 mm X | -5.000 mm X | 0.372 mm | 1.680 mm | 0.140 | 4.517 | MISMATCH |
| +Y | +5.003 mm Y | +5.000 mm Y | 0.715 mm | 0.678 mm | 0.331 | 0.948 | MISMATCH |
| -Y | -4.997 mm Y | -5.000 mm Y | 0.682 mm | 0.661 mm | 0.291 | 0.969 | MISMATCH |
| +Z | +5.022 mm Z | +5.000 mm Z | 0.908 mm | 0.731 mm | 0.917 | 0.805 | APPROXIMATE |
| -Z | -4.978 mm Z | -5.000 mm Z | 0.479 mm | 1.460 mm | 0.455 | 3.046 | MISMATCH |
| +Rx | +0.025 rad X | +0.025 rad X | 0.00353 rad | 0.00540 rad | -0.722 | 1.530 | MISMATCH* |
| -Rx | -0.025 rad X | -0.025 rad X | 0.00357 rad | 0.00561 rad | -0.732 | 1.571 | MISMATCH* |
| +Ry | +0.025 rad Y | +0.025 rad Y | 0.00451 rad | 0.00045 rad | 0.948 | 0.101 | APPROXIMATE* |
| -Ry | -0.025 rad Y | -0.025 rad Y | 0.00051 rad | 0.00115 rad | -0.955 | 2.262 | MISMATCH* |
| +Rz | +0.025 rad Z | +0.025 rad Z | 0.00365 rad | 0.00549 rad | 0.902 | 1.503 | APPROXIMATE* |
| -Rz | -0.025 rad Z | -0.025 rad Z | 0.00345 rad | 0.00548 rad | 0.886 | 1.588 | APPROXIMATE* |
| open | semantic OPEN | semantic OPEN | - | - | - | - | MATCH |
| close | semantic CLOSED | semantic CLOSED | - | - | - | - | MATCH |

`*` 旋转实际轨迹比较受 EEF orientation reference frame 差异影响，不能直接当作 Action Adapter 错误。

## 目标构造审计

- 平移六个方向的 LIBERO 与 Isaac 目标方向余弦为 `0.999974`～`0.999990`，目标幅值比约 `0.994`～`1.006`。
- 旋转六个方向的目标轴/符号余弦为约 `0.999990`～`1.000000`，目标幅值约 `0.025 rad`；乘法顺序两边均为 `R_delta @ R_current`。
- 因此没有确认 normalized action、scaling、sign 或 rotation multiplication order bug。

## EEF 参考点审计

LIBERO 使用 `robot0_eef_pos` 和 `robots[0].controller.ee_ori_mat`；Isaac 使用 `panda_hand` 世界位姿，位置额外加已审计的 `EEF_OFFSET_IN_HAND_M=[0,0,0.0951034858]`，姿态直接使用 `panda_hand` orientation。state 0 的位置差约 `0.431 mm`，但初始 orientation 相对差约 `1.571 rad`。这确认了旋转参考系尚未统一；不能把旋转 MISMATCH 直接归因为控制器或适配器。

## 分类结论

- 平移 MISMATCH：`TRACKING_MAGNITUDE_MISMATCH`，目标一致但 50 ms 实际跟踪不同。
- 旋转 MISMATCH：`REFERENCE_POINT_MISMATCH`，次级为 `TRACKING_MAGNITUDE_MISMATCH`；目标一致，但起始姿态参考系不同。
- `TARGET_MISMATCH`：未发现。
- `FRAME_OR_SIGN_MISMATCH`：未确认；需要多姿态校准后再判断。
- `ROTATION_COMPOSITION_MISMATCH`：未发现。
- `Action Adapter bug`：未确认。

## 最终决策

- 是否需要立即修复并重跑 Step 7A：否。
- 是否可能影响 Step 6 的 0/3：可能，但尚未证明；本审计不是任务成功率实验。
- 下一步：**B. State Mapping / EEF Calibration Audit**。
- 本阶段完成后停止，不自动启动下一阶段。
