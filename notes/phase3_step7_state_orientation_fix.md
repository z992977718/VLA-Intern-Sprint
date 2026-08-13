# Phase 3 / Step 7B.1：姿态映射状态

本轮没有写入任何固定 0.434 rad 或 90 度姿态补偿。

- LIBERO policy 输入姿态来源为 `robot0_eef_quat`，由 robosuite body API 读取并以 xyzw 格式进入 `LiberoProcessorStep`。
- Isaac 候选为 `panda_hand/tool_center` 的 USD world quaternion；采样中两者同向。
- Step 7B 五姿态中，Isaac hand 与 LIBERO policy-source body quaternion 的平均几何差为 0.434 rad、最大为 0.862 rad。
- 尝试单一固定旋转没有稳定改善，因此不能把它作为已证明的 rigid transform。

分类保持 `UNRESOLVED`。约 1.571 rad 的 controller matrix 差异是控制器 frame 诊断，不能误写成 Pi0.5 state 的固定 90 度 bug。
