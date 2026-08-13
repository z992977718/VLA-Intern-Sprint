# Phase 1–3 最终结果摘要

项目已完成从 **Model → Runtime → Robot → Evaluation → Failure Analysis** 的三阶段工程验证。Phase 3 收尾后，Franka / Isaac 主线正式冻结，不再追加 rollout、训练或调参。

## 三阶段结果

| 阶段 | 范围 | 最终状态 | 核心结果 |
| --- | --- | --- | --- |
| Phase 1 | LIBERO / MuJoCo policy learning | DONE | Pi0.5 在完整 40-task LIBERO 数据集上 continued fine-tuning 2,000 steps；重点任务 2k checkpoint 在 50 个固定初态上 46/50 |
| Phase 2 | Isaac / ROS 2 / Franka runtime integration | PASS | Observation、Policy、Action、Safety、PINK 与 Franka 形成真实 5-cycle receding-horizon runtime closed loop |
| Phase 3 | Cross-simulator evaluation 与 failure analysis | CLOSED OUT | Step 6 为 0/3；随后定位并修复 state、Safety、PINK 架构问题；scripted robot-side pipeline 当前为 ROBUST PASS；单次 post-fix Pi0.5 diagnostic 为 NO_CLEAR_IMPROVEMENT |

## Phase 1：LIBERO / MuJoCo

- 起始 checkpoint：`lerobot/pi05_libero_base`
- 训练数据：固定 revision 的完整 `lerobot/libero`
- 数据规模：40 tasks、1,693 episodes、273,465 frames
- Continued fine-tuning：2,000 steps
- 重点任务：`put both the alphabet soup and the tomato sauce in the basket`
- 2k checkpoint：50 个固定 initial states 中 46/50 成功

`46/50` 只属于同一指定 LIBERO 任务的固定初态评测。它不是完整 LIBERO benchmark 成功率，也不是 Isaac 成功率。

## Phase 2：Isaac / ROS 2 / Franka Runtime

完成的最小闭环包括：

```text
Camera + Robot State + Language
→ Observation Adapter
→ Pi0.5 Policy Adapter
→ 50×7 Action Chunk
→ 每轮只执行 action_chunk[0]
→ Action Adapter
→ Safety Layer
→ PINK IK
→ Franka
→ 新 Observation
```

5 个 cycle 均重新采集观测并真实调用 `predict_action_chunk`，runtime integration 为 **PASS**。该阶段没有任务物体和 task-success 判据，因此不能解释为抓取成功或迁移成功。

## Phase 3：任务迁移与系统化故障分析

### Step 6 Cross-simulator Rollout

- 3 个固定 initial states
- 每个最多 100 cycles，K=1
- 结果：0/3
- 终止：三次均 `HORIZON_REACHED`
- 行为分类：`FAILED_APPROACH`、`FAILED_GRASP`、`HORIZON_REACHED`
- 两个目标物均无有效运动
- Experimental Pipeline：PASS
- Task Transfer：FAIL

### 接口与 Robot-side 定位

Action semantics audit 没有确认 sign、scaling 或 Action Adapter bug。

State Mapping 修复后，位置误差如下：

| 集合 | 修复前 mean / max | 修复后 mean / max |
| --- | ---: | ---: |
| Calibration | 37.870 / 70.814 mm | 7.874 / 8.207 mm |
| Hold-out | 62.852 / 79.705 mm | 7.800 / 7.898 mm |

夹爪状态改为 LIBERO-compatible mirrored representation：

```text
Isaac [finger1, finger2] → [finger1, -finger2]
```

Orientation mapping 仍为 `UNRESOLVED`；最大 image-state skew 约 `0.15 s`，作为已知限制保留。

Scripted Oracle 的原始结果为 Alphabet soup 3/3、Tomato sauce 0/3。Tomato 失败先被定位到 joint-limit 浮点边界的 Safety false positive，清除后又定位到 PINK 错误包含 finger joints。采用浮点安全比较并将 PINK 从 9D arm+finger 改为 7D arm-only、保持夹爪独立后，Tomato 正式 post-fix validation 为 3/3。结合既有 Alphabet 3/3，当前 scripted robot-side manipulation pipeline 为 **ROBUST PASS**。

这些 Oracle 结果不使用 Pi0.5、视觉识别或语言决策，不能写成 Pi0.5 成功率。

### Post-fix Pi0.5 Diagnostic

只运行了一个不计入正式 benchmark 的诊断 episode：Step 6 state 0、100 cycles、K=1。结果为 `HORIZON_REACHED`，没有 task success、目标物运动或可信抓取；无 Safety violation、无 IK failure；99/100 cycles 出现 action clipping，64 cycles 为 close command，离 tomato 最近的 close attempt 约 0.201665 m。行为变化记为 `NO_CLEAR_IMPROVEMENT`。

该单次诊断说明：清除已知 robot-side blockers 后，Pi0.5 cross-simulator 行为仍没有表现出明确改善。它不能进一步证明 Pi0.5 本身无效。

## 已知限制

1. Orientation mapping 仍未解决；
2. image-state skew 最大约 0.15 s；
3. LIBERO/MuJoCo 与 Isaac/PhysX 存在 renderer、视觉和动力学差异；
4. controller 与 embodiment 不同；
5. 目标物 collision 与 camera calibration 仍含近似；
6. post-fix Pi0.5 只有一个 diagnostic episode；
7. action clipping 为 99/100 cycles，未继续归因；
8. completion-file handshake 存在竞态：100 次 inference 与 100 cycles 均已完成，但顶层完成文件检查早于文件生成不到一秒，导致原始 exit code 1。它不改变已完成 episode 的结果，但属于 tooling limitation。

## 最终工程决策

```text
FREEZE_FRANKA_ISAAC_MAINLINE
```

主要 robot-side blockers 已经清除，post-fix Pi0.5 diagnostic 未显示明确改善，继续深挖 Franka / Isaac 的项目收益偏低。禁止追加 Franka/Isaac rollout、训练或调参；既有结果和日志保持冻结。

下一主阶段仅记录为 `SO-101_REAL_ROBOT / PLANNED_NOT_STARTED`，本轮没有创建代码或启动实验。
