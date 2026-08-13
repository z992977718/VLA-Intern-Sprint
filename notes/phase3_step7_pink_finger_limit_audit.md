# Phase 3 / Step 7C.4：PINK Finger-Joint Configuration Limit 静态审计

## 审计范围

本阶段只读取当前项目代码、RTX 5090 上实际安装的 Isaac Sim 6.0.1 / PINK extension 0.1.3 源码、Franka URDF 和 Step 7C.2/7C.3 既有日志。没有启动 Isaac、Pi0.5、训练或新 trial，也没有修改 controller、tolerance、joint limit、physics、trajectory 或冻结结果。

## 真实调用链

```text
robot.get_dof_positions()                         # Isaac 当前 9D state，float32
  -> estimated_state()
  -> PinkIKController._extract_joint_positions() # 9 个 controlled joints
  -> Python float / np.array                      # 转为 float64
  -> map_joint_positions_to_pinocchio()
  -> Configuration.update(q)
  -> _solve_ik()
  -> Configuration.check_limits(tol=1e-6)        # QP solve 前
  -> build_ik / QP solve                          # 本次未到达
  -> integrate_inplace                            # 本次未到达
```

报错值并非 solve 后产生。它进入 `_solve_ik()` 前已经存在于 PINK current configuration。

## 为什么 configuration 有 fingers

Bundled Franka URDF 中两根 finger 都是独立的 prismatic joint，limit 为 `[0, 0.04] m`。URDF 注释明确说明已经移除了 finger2 对 finger1 的 mimic 元素。

`configuration_loader._get_controlled_joint_names()` 会收集所有 `nq > 0` 的 joint，所以默认 controlled list 是：

```text
0 panda_joint1
1 panda_joint2
2 panda_joint3
3 panda_joint4
4 panda_joint5
5 panda_joint6
6 panda_joint7
7 panda_finger_joint1
8 panda_finger_joint2
```

项目又把相同的完整 `JOINT_NAMES` 作为 `robot_joint_space`，因此 PINK configuration、configuration limits、velocity vector、PostureTask 和输出全部是 9D。

## fingers 是否主动被求解

回答为 `YES`，但要区分 task：

- `panda_hand` FrameTask：finger 位于 panda_hand 下游，因此不会利用 finger 改变 hand pose；
- PostureTask：使用完整 nv 维 identity Jacobian，因此会为 finger 产生姿态回正 velocity；
- existing descent step 0：finger2 actual=`0.040000006556510925 m`，PINK target=`0.04000000283122063 m`，可见 target 与 actual 不同，velocity 非零且方向向下。

项目随后先写完整 PINK target，再写 `[0.04, 0.04]` 到 indices `[7,8]`。Isaac 的 selected-index 写入是 read-modify-write，因此第二次写入覆盖 PINK finger target。merge ordering 没有错，但 configuration/QP 层仍未解耦。

## PINK limit check

实际位置：

- Isaac wrapper：`pink_ik_controller.py::_solve_ik()` line 524
- PINK：`pink/configuration.py::Configuration.check_limits()` lines 167–195

逻辑：

```text
q < lower - 1e-6 或 q > upper + 1e-6 -> raise NotWithinConfigurationLimits
```

检查对象是 solve 前的 current q，不是 velocity、target 或 integrated q。q 和 limits 都是 float64。

finger2 是 prismatic joint，因此这里的 tolerance 和 excess 单位应写米。上游 docstring 和项目通用字段中的 “rad” 只是单位标签不严谨，不是本次失败根因。

## 根因结论

已确认的直接根因：

> PINK 收到的 Isaac finger2 current state 已经超过 `upper + 1e-6 m`；项目又把独立 gripper 包含在 arm IK configuration 中，所以与 arm pose 无关的 finger limit check 在 QP solve 前阻断整个 arm IK。

更底层的 actual-position overshoot 机制未被完整记录。最终 gripper target 为 float32 `0.04`，而历史 telemetry 已证明 measured current 偶尔高于该 target；因此 drive tracking overshoot 是可能解释，但不能静态确认 PhysX 内部原因。

## ROI 与建议

判定为局部项目架构问题，值得做一次有界修复，而不是扩大 tolerance：

1. 把 project-side PinkRobot `controlled_joint_names` 限定为 7 个 `ARM_JOINTS`；
2. PinkIKController 使用 7D arm `robot_joint_space`；
3. fingers 继续只由独立 gripper path 控制；
4. 不修改 upstream PINK、physical limit、Safety tolerance、physics 或 trajectory；
5. 获得明确授权后只运行一次 `DIAGNOSTIC / NOT COUNTED` Tomato trial。

若该方案实际要求 fork upstream、复杂 reduced model 或 controller redesign，则立即停止 Franka deep dive，记录 known limitation。当前 Pi0.5 diagnostic rollout=`NO`。
