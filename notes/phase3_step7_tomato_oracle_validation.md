# Phase 3 / Step 7C.6：Tomato 固定协议解耦后验证

## 最终结论

`Step 7C.6 = PASS`。

7D arm-only PINK 与独立 gripper control 在三个独立 hard-reset Tomato 正式 trial 中获得 `3/3 SUCCESS`。根据预先冻结的解释规则：

- Tomato post-decoupling validation：`ROBUST PASS`
- basic robot-side scripted Oracle pipeline：`ROBUST PASS`

历史结果继续保留：

- Step 7C Alphabet：`3/3`
- Step 7C original Tomato：`0/3`
- Step 7C.3 Tomato post-fix：`0/3`
- Step 7C.5 diagnostic：1 次 diagnostic success，`NOT COUNTED`
- Step 7C.6 formal after：`3/3`

## 固定代码和协议

运行前冻结并在三次 trial 后复核：

- `isaac_step7_grasp_oracle.py`
- `joint_safety_float_limits.py`
- `isaac_step6_scene_gate.py`
- `phase3_step6_common.py`
- `pink_arm_only.py`
- `franka_arm_only.urdf`
- 已安装的 `pink_ik_controller.py`

运行前后 SHA-256 diff 为 0 字节。三个 trial 期间没有修改代码、参数或轨迹。

固定设置包括 tomato asset、initial state 0、scene、pre-grasp、descent、grasp、close、lift、hold、physics、PINK cost、OSQP、Safety 和 success metric。每个 trial 都由新的 Isaac 进程 hard reset；没有筛选 seed、失败补跑或第 4 次 trial。

继承的修复只有：

1. Step 7C.3 的 2-ULP floating-point-safe Safety；回归仍为 `13/13 PASS`。
2. Step 7C.5 的 7D arm-only PINK；finger joints 继续走独立 gripper command 与独立 Safety。

## 三次正式结果

三个 trial 的共同结果：

- pre-grasp：PASS，approach step 0~239。
- descent：PASS，step 0~199 全部完成。
- PINK：`nq=nv=7`，只含 `panda_joint1~7`。
- PINK solve failure：0。
- finger configuration-limit failure：0。
- Safety violation：0。
- gripper close：执行并完成。
- 最终 finger1/finger2：约 `0.035155/0.035180 m`。
- object max-lift position：`[-0.0877402, 0.0591343, 0.6247144] m`。
- object final position：`[-0.0922731, 0.0582324, 0.6240760] m`。
- 最大竖直位移：`146.5309 mm`。
- hold 后最终竖直位移：`145.8925 mm`。
- 固定 lift threshold：`60 mm`。
- lift：SUCCESS。
- OOM：无。

三次 runtime 分别约为 `19.524 s`、`20.521 s`、`19.820 s`。三次结果完全一致来自固定初始状态和确定性控制协议；本项目只报告实际观测，不将一致结果扩展解释为其他 initial state 或其他物体上的稳健性。

没有 contact sensor，因此不能写成 `direct contact measured`。允许的表述是：`object motion / grasp-lift behavior observed`。

## Before / Diagnosis / Fix / After

```text
BEFORE
Alphabet 3/3
Tomato 0/3
    ↓
Failure Localization
    ↓
Bug 1: floating-point Safety false positive
    ↓
2-ULP Safety fix + 13/13 regression PASS
    ↓
New blocker: PINK finger configuration limit
    ↓
Static audit
    ↓
Confirmed architecture bug:
finger joints incorrectly included in arm IK
    ↓
Fix: 9D -> 7D arm-only PINK, gripper independent
    ↓
Single diagnostic: SUCCESS / NOT COUNTED
    ↓
FORMAL AFTER: Tomato 3/3 / ROBUST PASS
```

## 视频

- `assets/videos/phase3_step7_oracle_tomato_validation_00.mp4`
- `assets/videos/phase3_step7_oracle_tomato_validation_01.mp4`
- `assets/videos/phase3_step7_oracle_tomato_validation_02.mp4`

每段由对应 trial 的 66 张按时间排序的原始帧以 15 FPS 编码，未剪辑、未拼接其他 trial。

## 解释边界和下一步

本实验完全没有使用 Pi0.5，因此不能解释为 Pi0.5 success/failure，也不能证明 Step 6 Pi0.5 `0/3` 是由这两个 robot-side bug 造成。

当前可以说：已确认的 major robot-side scripted manipulation blockers 已清除到足以开展一次 Pi0.5 diagnostic rollout 的程度。推荐下一步为：

`ONE_POST_STATE_MAPPING_PI05_DIAGNOSTIC_ROLLOUT`

本阶段没有执行该下一步，必须等待新授权。
