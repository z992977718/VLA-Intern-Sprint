# Phase 2 / Step 1 结果总结

## 结论

PASS。已在远程 RTX 6000D 上完成 Isaac Sim 6.0.1 + ROS 2 Humble + 官方 Franka Panda 的最小关节控制闭环。

## 实测链路

```text
ROS 2 /joint_command
→ Isaac Sim ROS 2 Bridge
→ IsaacArticulationController
→ Franka Panda physics movement
→ ROS 2 /joint_states
```

## 状态证据

- 初始状态：`[0.012, -0.5686, 0.0, -2.8109, 0.0, 3.0368, 0.741]`
- 目标状态：`[0.0, -0.45, 0.0, -1.75, 0.0, 1.3, 0.78]`
- 结果状态：`[0.0001, -0.4489, 0.0, -1.7715, 0.0, 1.3560, 0.7796]`
- 最大绝对误差：`0.0560 rad`
- `robot_moved=true`，`target_reached=true`，ROS 节点退出码 `0`。

## 运行状态

- Isaac Sim startup：PASS
- RaytracedLighting / RTX runtime：PASS
- Franka USD：PASS
- Physics：PASS
- ROS 2 Bridge：PASS
- `/joint_states`：PASS
- `/joint_command`：PASS
- 闭环反馈：PASS
- GPU 总显存：85,651 MiB
- 实测 peak GPU VRAM：577 MiB（最终成功一键复现的 23 个 `nvidia-smi` 原始采样点；仅代表本简单场景）
- OOM：NO
- Remote visualization：NOT CONFIGURED

## 边界

没有启动 Pi0.5、Camera、MoveIt、抓取、Pick-and-place、Isaac Lab training 或 Phase 2 / Step 2。
