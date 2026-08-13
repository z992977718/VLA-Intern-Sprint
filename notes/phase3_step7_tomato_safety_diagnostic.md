# Phase 3 / Step 7C.2：Tomato Safety Telemetry Diagnostic

## 目的与边界

本轮只运行一次 `DIAGNOSTIC / NOT COUNTED` tomato trial，用于定位 Step 7C 三次正式 tomato trial 在 `descent step 0` 的聚合 `SAFETY_STOP`。

本轮没有修改冻结的正式统计：

- Alphabet：`3/3`
- Tomato：`0/3`
- Overall：`3/6`

没有调用 Pi0.5 或 `predict_action_chunk`，没有训练、LoRA、RL、Step 6 重跑，也没有修改 PINK、轨迹、目标姿态、物理、质量、摩擦、碰撞、joint limits、`0.05 rad` joint-delta threshold 或 Safety 开关。

## 实现方式

为避免影响冻结的 `isaac_step7_grasp_oracle.py`，新增独立 telemetry-only 脚本：

```text
phase3/scripts/isaac_step7_tomato_safety_diagnostic.py
```

脚本复用原 Oracle 的：

- Step 6 state 0 dynamic scene；
- tomato live collider geometry；
- pre-grasp 和 descent target 公式；
- top-down orientation；
- PinkIKController + OSQP；
- 240 步 approach；
- 原 200 步 descent setpoint；
- `MAX_JOINT_STEP_RAD=0.05`；
- 原 physics timestep 和 gripper open target。

区别只在诊断控制：每次 Safety decision 前原子写出 PINK、joint、delta、limit 和 EEF telemetry；若 Safety Stop 立即退出。若未复现，最多执行前三个 descent control step 后主动停止，不进入 close/lift。

## 实际运行

- GPU：NVIDIA GeForce RTX 5090
- Trial：1 次，`DIAGNOSTIC / NOT COUNTED`
- Runtime：`34.616132 s`
- Pre-grasp：完成
- Descent：进入
- Descent step：`0`
- Outcome：`SAFETY_STOP_LOCALIZED`
- 退出码：`0`
- 完成后 GPU：`0 MiB`，未残留 Isaac/Pi0.5 进程

## PINK 输出

- Solve status：`TARGET_RETURNED`
- `PINK_TARGET_FINITE=YES`
- `finite_joint_actual=true`
- `finite_joint_target=true`
- 没有 NaN、`+Inf` 或 `-Inf`

因此 `NONFINITE_JOINT_TARGET` 被排除。

## Joint delta

最大绝对 joint delta：

```text
panda_joint6
abs(delta) = 0.04410219192504883 rad
threshold  = 0.05 rad
margin     = 0.005897808074951172 rad
```

九个 joint 均未超过 `0.05 rad`，因此 `JOINT_DELTA_LIMIT` 被排除。

## Joint lower limit

九个 joint 均满足 `target >= lower`，没有 lower-limit violation，因此 `JOINT_LOWER_LIMIT` 被排除。

## Joint upper limit

唯一 violation：

```text
joint  = panda_finger_joint2
index  = 8
actual = 0.040000006556510925 rad
target = 0.04000000283122063 rad
upper  = 0.03999999910593033 rad
excess = 0.000000003725290298461914 rad
```

目标比上限高 `3.725290298461914e-09 rad`。当前 Oracle 直接执行严格比较：

```python
joint_target > upper[indices]
```

因此这个浮点精度量级的 upper-limit overshoot 足以拒绝整个 descent step 0。

## 精确根因

```text
Exact Safety Trigger = JOINT_UPPER_LIMIT
Confirmed root cause = YES
Root cause category  = JOINT_UPPER_LIMIT
Trigger joint        = panda_finger_joint2
```

根因是 PINK 全 DOF finger target 与 Isaac runtime finger upper limit 在 float 表示上的边界差异，加上 Safety 无数值容差的严格比较。

它不是：

- `0.05 rad` joint-delta 问题；
- PINK 没有返回解；
- non-finite target；
- arm joint 越界；
- physics / friction / mass / collision；
- gripper 机械抓取能力；
- Pi0.5 / visual / timestamp skew。

## 最小修复建议（本轮未执行）

建议在未来获授权后：

1. 让 joint target 和 runtime limits 使用一致的比较精度；
2. 定义只覆盖 float 表示误差的微小 `JOINT_LIMIT_EPS`；
3. 仅当目标在 `limit ± EPS` 内时夹回精确 lower/upper limit；
4. 超过 tolerance 的真实越界仍触发 Safety；
5. 保持 `MAX_JOINT_STEP_RAD=0.05` 不变；
6. 保留本轮明确 reason code 和 telemetry。

这不是放宽物理关节限位，而是避免一个数值上只高 `3.7e-09 rad` 的目标被误判；实际下发值仍不得超过 runtime limit。

## 是否继续

- 是否应做一次最小修复：`YES`，但必须等用户另行授权。
- 修复后是否值得运行 3 次相同协议 tomato Oracle：`YES`，保存到独立 post-fix 目录，不覆盖或改写原 `0/3`。
- 现在是否运行 Pi0.5 diagnostic rollout：`NO`。
- Step 7C.2：`PASS`，仅表示精确触发条件已成功定位。

## 证据

```text
results/phase3_step7/tomato_safety_diagnostic/
├── environment.txt
├── diagnostic_config.json
├── pink_output.json
├── joint_telemetry.json
├── safety_decision.json
├── descent_step0.json
├── run.log
├── run_status.json
└── summary.md
```
