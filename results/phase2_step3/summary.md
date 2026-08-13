# Phase 2 / Step 3 实验总结

## 最终结论

**Step 3：PASS。** 真实 Isaac/ROS 2 静止 Observation 已通过项目 Policy Input Adapter 和 LeRobot/Pi0.5 真实 processor，Phase 1 2k checkpoint 连续 3 次真实执行 `predict_action_chunk`，均得到有效的 50×7 Action Chunk。没有发布或执行任何预测动作。

## 输入

- 外部相机：256×256 RGB8 → `observation.images.image`
- 手腕跟随视角：256×256 RGB8 → `observation.images.image2`
- 状态：9D named joint state + Isaac `panda_hand` `/World` 变换 → 8D `[xyz, axis-angle, finger qpos]`
- 语言：`move the robot arm`
- 两张图与 `/joint_states` 最大时间差：0.05 秒
- schema compatibility：PARTIAL
- 同步限制：两张 ROS 图与关节状态最大差 0.05 秒；EEF 变换独立保存。本次全程静止可用于接口测试，移动场景不能沿用该同步假设。

## Pi0.5

- checkpoint：`results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model`
- policy：Pi0.5，BF16，CUDA
- checkpoint action：7D，chunk size 50
- 真实调用次数：3
- 每次 shape：`[1,50,7]`
- 保存的 `action_chunk.npy` shape：`[50,7]`
- 全部 Action：finite
- latency：407.157 / 186.766 / 186.218 ms
- mean / median / p95：260.047 / 186.766 / 385.118 ms
- model load：99.004 s
- Torch peak allocated / reserved：8.870 / 9.201 GiB
- `nvidia-smi` 进程占用峰值快照：10,015 MiB
- OOM：NO

## Action 审计

Pi0.5 7D 是 LIBERO 相对 `OSC_POSE`：EEF position delta 3D、EEF axis-angle delta 3D、gripper 1D。Isaac 当前 `/joint_command` 是七个 arm joint 的绝对位置。因此两者是 MISMATCH，不能直接执行。

## 调试记录

1. 初次完整 wrapper 在 source ROS setup 时触发 `set -u` 兼容问题，未进入模型；已修复环境加载边界。
2. 初次 policy-only 输入的嵌套 quaternion 缺少单样本 batch 维，真实 `LiberoProcessorStep` 以 `(4,)` 而非 `(B,4)` 拒绝；失败日志保留，修复只增加 batch 维。
3. 三次推理和全部核心结果保存完成后，写 `environment.txt` 时发现远程项目根目录不是 Git 仓库，环境清单步骤返回 128。未重复运行模型；本地脚本已把项目 Git commit 改为可选字段。

## 边界

- Images：PARTIAL
- Robot State：PARTIAL
- Language：MATCH
- Policy Input：PARTIAL
- Pi0.5 Runtime：PASS
- Action output：PASS
- Action → Isaac Controller：MISMATCH
- action published/executed：NO
- Rollout/Evaluation：未执行
- LeRobot upstream：未修改

完成后已停止 Isaac 和 Pi0.5；远端最后一次成功检查为 GPU 0 MiB、0% utilization，无相关计算进程。
