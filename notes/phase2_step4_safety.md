# Phase 2 / Step 4 安全层

安全链位于 Pi0.5 与 Isaac controller 之间。任一检查失败时不发送 motion target。

## 检查项

- action shape 必须为 7，所有数值必须 finite；
- 平移控制输入逐维限制到 ±0.1，对应最多 ±5 mm；
- 旋转控制输入逐维限制到 ±0.05，对应最多 ±0.025 rad；
- smoke workspace：x `[0.20,0.70]` m、y `[-0.30,0.30]` m、z `[0.20,0.80]` m；
- PINK 必须成功返回 finite joint target；
- joint target 必须位于 Isaac USD 返回的 Franka joint limits；
- 每次 PINK 输出与当前关节位置的最大差不得超过 0.05 rad；
- Observation EEF 与执行环境稳定后的 EEF 距离不得超过 5 mm；
- wrapper 超时，失败即退出；只允许一次 inference 和 `action_chunk[0]`。

## 阈值依据

robosuite 完整平移尺度是每轴最多 5 cm，旋转是每轴最多 0.5 rad。当前只验证一个动作，不执行闭环，因此分别使用其 10% 和 5% 作为保守 smoke 范围，即最多 5 mm 与 0.025 rad。workspace 仅包围当前 Franka 前方安全区域，不声称为完整机械臂可达域。关节绝对限位直接读取 Isaac Franka USD；0.05 rad 单次 joint displacement 是项目侧额外保守门。

gripper 映射：LIBERO 正值关闭、负值打开；Isaac 双指 `0 m=closed`、`0.04 m=open`。中性值保持当前双指均值。本阶段没有夹取物体。
