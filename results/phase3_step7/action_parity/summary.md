# Step 7A 动作一致性审计摘要

- 运行状态：完成
- Pi0.5：未调用
- 训练：未执行
- 任务 rollout：未执行
- canonical actions：14 个，每个独立 reset
- 总体判断：`MISMATCH`（实际单步跟踪矩阵）
- 夹爪：open/close `MATCH`
- 平移：2 个 APPROXIMATE，4 个 MISMATCH
- 旋转：3 个 APPROXIMATE，3 个 MISMATCH
- Safety/PINK/关节限位：全部通过
- OOM：否

详细数值见 `parity_matrix.json`、`translation_comparison.json`、`rotation_comparison.json` 和 `gripper_comparison.json`。

注意：单个 0.05 秒控制周期的实际轨迹受两套模拟器的控制器动力学、初始姿态和坐标标定影响。该结果不直接证明 Pi0.5、VLM 或语言理解故障，也不直接解释 Step 6 的 0/3。
