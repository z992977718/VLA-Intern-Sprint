# Step 7A.1 动作不一致定位

已离线分析 Step 7A 保存的 JSON；未运行仿真、Pi0.5、训练或 rollout。

结论：目标构造未发现缩放/符号/左乘次序错误。平移的短时差异归为 TRACKING_MAGNITUDE_MISMATCH；旋转的初始 EEF frame 姿态差异已确认，因此其实际轨迹比较需要先完成 EEF calibration。建议 B：State Mapping / EEF Calibration Audit，不执行修复。
