# Phase 3 / Step 7A：LIBERO → Isaac 动作一致性审计

## 结果

结果目录：`results/phase3_step7/action_parity/`。每个动作都独立 reset，完成 14 个 canonical action 的实际测量。

| 类别 | 结果 |
|---|---|
| 平移 | `+X`、`+Z` 为 APPROXIMATE；`-X`、`+Y`、`-Y`、`-Z` 为 MISMATCH |
| 旋转 | `+Ry`、`+Rz`、`-Rz` 为 APPROXIMATE；`+Rx`、`-Rx`、`-Ry` 为 MISMATCH |
| 夹爪 | `open`、`close` 均为 MATCH |
| 总体 | `MISMATCH`（按单步实际轨迹标准） |

LIBERO 端的实际移动量约为 0.37–0.91 mm，Isaac 端约为 0.45–1.68 mm；这是控制器动力学和单步时长下的跟踪结果，不等于目标缩放本身错误。夹爪的 `-1/+1` 语义在两端一致。

## 安全与限制

所有 Isaac 案例均通过 Safety、PINK、关节限位和有限值检查；没有 OOM。Isaac 资产日志仍有 living-room table bump texture 缺失警告，但不阻塞本次动作测量。该审计不能解释 Step 6 的 0/3 任务结果，只能说明动作语义/短时跟踪仍需进一步的 State Mapping / EEF Calibration 审计。

## 结论

Step 7A：`PARTIAL`。源码层面的 OSC_POSE 缩放、左乘姿态组合和夹爪符号已确认；但跨模拟器单步实际 EEF 方向/幅值未达到全量 MATCH。下一步应先做 State Mapping / EEF Calibration Audit，不应直接继续任务 rollout 或修改 Pi0.5。
