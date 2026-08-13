# Phase 2 / Step 4 控制器选择

## 选择

使用 Isaac Sim 6.0.1 的当前 API：

```text
isaacsim.robot_motion.pink
PinkIKController
load_pink_supported_robot("franka")
isaacsim.robot_motion.experimental.motion_generation.RobotState
```

选择原因：当前服务器安装的 Isaac 6.0.1 自带 PINK 0.1.3、Franka 配置和 OSQP。官方示例直接使用 `panda_hand` 的 world pose 目标，经 differential IK 输出 Franka joint position targets。该路线属于 Isaac 6 新增的 Robot Motion API，不是 deprecated Lula 路线。

实际安装源码和官方 example `ik_controller/scenario.py` 已保存到 `results/phase2_step4/source_audit/pink/`。官方文档：

- https://docs.isaacsim.omniverse.nvidia.com/6.0.1/pink/tutorial_ik_controller.html
- https://docs.isaacsim.omniverse.nvidia.com/6.0.0/py/source/extensions/isaacsim.robot_motion.pink/docs/index.html

本项目没有自行实现 Jacobian、伪逆或完整 IK 求解器，也没有使用 MoveIt。
