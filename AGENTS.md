# 项目目标

这是一个为期 7 天的实习准备项目。

目标：使用 LeRobot 对 Pi0.5 VLA 策略进行微调，并在 LIBERO 模拟基准中进行评测。SmolVLA 是可选基线，并非运行 Pi0.5 的必要前置步骤。

本项目**不是真实机器人项目**。

## 长期阶段边界

```text
Phase 1:
π0.5 + LeRobot + LIBERO
DONE

Phase 2:
Isaac Sim + ROS 2 + Manipulator Deployment
IN PROGRESS
```

Phase 1 的 checkpoint、原始实验结果与结论已经冻结，不得因 Phase 2 工作修改、删除或重新生成。

Phase 2 / Step 1 只建立 Isaac Sim、ROS 2、Franka Panda、joint command 和 joint-state feedback 的最小闭环。此步骤禁止接入 Pi0.5、Camera、MoveIt、抓取、Pick-and-place、Isaac Lab training 或真实机械臂。

Phase 2 / Step 1 已于 2026-08-12 完成并通过验收。除非用户明确启动 Step 2，否则不得继续启动 Isaac GPU 任务或接入 Camera、Pi0.5、MoveIt、抓取等后续功能。

Phase 2 / Step 2 已于 2026-08-12 完成并通过验收：两路 256×256 RGB、`/joint_states`、语言字段和 Observation Snapshot 已建立。第二路仅是跟随 `panda_hand` 的虚拟视角，不是已标定的刚性 eye-in-hand 相机。

Phase 2 / Step 3 已于 2026-08-12 完成并通过接口/runtime 验收：项目侧 Policy Input Adapter 使用 LeRobot 真实 LIBERO processor 和 2k Pi0.5 checkpoint，3 次真实 `predict_action_chunk` 均输出有限的 50×7 Action Chunk。该步骤没有发布或执行任何 VLA Action。

Phase 2 / Step 4 已于 2026-08-12 完成并通过验收：实际安装源码确认 LIBERO `OSC_POSE` 语义，Isaac Sim 6.0.1 官方 `PinkIKController` 完成合成坐标、姿态与夹爪验证；随后只进行一次 Pi0.5 inference，并只执行 `action_chunk[0]`。剩余49步未执行，没有第二次 inference，没有形成 VLA closed loop。

Phase 2 / Step 5 已于 2026-08-12 完成并通过 runtime 验收：同一 Isaac 场景中完成严格 5 轮 receding-horizon 闭环；每轮重新采集两路 RGB 和 8D state，真实调用一次 Pi0.5 `predict_action_chunk`，只执行 `action_chunk[0]`，再采集下一轮观测。5 轮 Safety 与 PINK 均通过，无 OOM；没有布置目标物体或评测任务成功。

当前必须停在 Step 5。除非用户明确启动下一阶段，否则禁止：继续自动 inference、超过 5 个 Cycle、执行完整 Action Chunk、建立任务场景或任务 Rollout、抓取、成功率评测、MoveIt、RL、LoRA、Full Fine-Tuning、TensorRT 或真实机械臂控制。Step 5 的 PASS 只表示 closed-loop runtime 工作，不代表任务成功、LIBERO transfer、zero-shot manipulation 或跨域泛化。

# 执行环境

本项目严格区分两个执行环境。

## 本地电脑

本地电脑**仅用于**：

- Codex 项目管理；
- 阅读源码；
- 编辑脚本；
- 维护笔记与文档；
- Git 操作；
- 准备命令。

不得在本地 Windows 或 WSL 中安装完整的 LeRobot / SmolVLA / LIBERO 训练环境。

不得将本地 RTX 3060 作为主要训练 GPU。

## 主要远程 GPU 服务器

配备 NVIDIA RTX 6000D 的新 AutoDL Linux 服务器，是以下工作唯一的主要执行环境：

- PyTorch CUDA 运行环境；
- LeRobot 运行依赖；
- Pi0.5；
- 可选 SmolVLA 基线实验；
- LIBERO / MuJoCo；
- 数据集加载；
- 微调；
- Rollout；
- Evaluation；
- GPU profiling。

Phase 2 的 Isaac Sim、ROS 2、Franka Panda 仿真和关节控制验证也只允许在该远程服务器执行。

持久化项目与数据根目录为 `/root/autodl-tmp`，项目路径为 `/root/autodl-tmp/VLA-Intern-Sprint`。

## 旧 RTX 4090 服务器

旧 RTX 4090 服务器已退出主要执行环境，可以保持关机。不得在该服务器启动新训练。其已验证的模型、数据集、LIBERO assets、tokenizer cache 和结果日志已迁移至 RTX 6000D，并于 2026-08-11 使用全文件哈希清单完成校验。

远程服务器连接不可用时，只能检查源码并准备命令。不得用安装本地训练环境来替代远程运行。

任何需要 PyTorch CUDA、LeRobot 运行依赖、Pi0.5、SmolVLA、LIBERO、MuJoCo、训练、Rollout、Evaluation 或 GPU profiling 的命令，都必须标记为“仅远程执行”。在远程 GPU 服务器输出得到验证之前，不得标记为成功。

# 主要约束

1. 不得声称完成真实机器人部署。
2. 优先使用 LeRobot / LIBERO 官方 API。
3. 不得静默修改依赖版本。
4. 修改上游 `lerobot/` 前必须先解释原因。
5. 优先在 `scripts/` 下添加轻量封装脚本。
6. 将重要命令记录到 `notes/commands.md`。
7. 记录环境版本和 Git commit hash。
8. README 中的指标必须来自真实日志。
9. 不得编造成功率、延迟或硬件结果。
10. 解释应当对初学者友好，同时保持技术准确。
11. 不得为 VLA 运行栈创建本地 Windows / WSL 虚拟环境。
12. 本地源码静态检查结果必须与远程运行验证结果分开记录。

# 工作流程

每项任务按以下顺序执行：

1. 先检查代码与文档；
2. 说明发现；
3. 提出最小改动；
4. 执行并测试；
5. 报告准确结果；
6. 按需更新笔记。

# 项目产物

- `README.md`
- `notes/concepts.md`
- `notes/daily_log.md`
- `notes/project_facts.md`
- `scripts/`
- `results/`

## 最新阶段边界：Phase 3 / Step 6

Phase 3 / Step 6 已于 2026-08-12 完成：同一 LIBERO 语义任务在 Isaac Sim 中完成 3 个固定 initial state、每个最多 100 cycle 的 cross-simulator 闭环。Experimental Pipeline 为 PASS，Policy Task Result 为 0/3，Task Transfer 为 FAIL；三回合均为 `HORIZON_REACHED`，无 OOM、无人工干预。

本节是当前最新边界，取代前文“必须停在 Step 5”的旧状态描述。现在必须停在 Step 6。除非用户明确启动 Step 7，否则禁止继续 Isaac/Pi0.5 自动推理、追加 episode、修改本次 success detector、为了成功率调参或重跑、训练/LoRA/Full Fine-Tuning、K 对比、RL、TensorRT 或真实机械臂控制。

Step 6 只支持以下表述：LIBERO → Isaac cross-simulator/cross-environment task evaluation；实验管线通过，但同语义任务在当前协议中 0/3。不得声称 unseen-task、zero-shot new-task、open-world generalization、sim-to-real，或把 pipeline PASS 写成 policy task success。

## 最新阶段边界：Phase 3 / Step 7C

Phase 3 / Step 7C 已完成：Scripted Grasp Oracle 在不使用 Pi0.5、视觉识别或语言决策的情况下，复用 Step 6 initial state 0 和真实 Isaac/Franka/PINK/PhysX 链路完成固定六次 hard-reset 试验。alphabet soup 为 3/3，tomato sauce 为 0/3（均在 descent 阶段 SAFETY_STOP），总体 3/6，结论为 `PARTIAL`。

Step 7C 的结论只表示 robot-side scripted grasp pipeline 对 alphabet soup 已验证、对 tomato sauce 尚未验证。不得把它写成 Pi0.5 成功率、LIBERO transfer、跨域泛化或真实机器人部署结果。不得修改固定六次原始结果、为了成功率追加 trial、调摩擦/质量/碰撞体/夹爪力/solver，或把 tomato 失败归因于 Pi0.5、视觉模块或 timestamp skew。

当前必须停在 Step 7C。除非用户明确启动后续诊断，否则禁止启动 Pi0.5 diagnostic rollout、训练、LoRA、RL、Full Fine-Tuning、Step 6 重跑、修改 success detector、物体 teleport/attach、或真实机械臂控制。Step 7C 不使用相机和 observation，因此 Step 7B 的 `0.15 s` image-to-joint skew 不属于本实验的解释变量。

## 最新阶段边界：Phase 3 / Step 7C.3

Phase 3 / Step 7C.3 已于 2026-08-13 完成。项目只修复了 Step 7C.2 确认的 joint-limit 浮点比较 false positive：runtime target/limit/comparison dtype 均为 `float32`，容差采用每个 limit 的 `2 ULP`，finger limit 附近为 `7.450580596923828e-09 m`。正式纯数值测试 `13/13 PASS`；三次 Tomato post-fix trial 的 descent step 0 均通过项目 Safety，证明原 `JOINT_UPPER_LIMIT` false positive 已消失。finger joint 是 prismatic joint，因此其数值单位为米，历史通用 `_rad` 字段名不代表真实单位。

三次 Tomato post-fix trial 随后均在 descent 中段出现新的 PINK 内部 configuration-limit `IK_FAILURE`，Tomato AFTER 仍为 `0/3`，完整 descent/grasp/lift 均为 `0/3`。结合冻结的 Alphabet `3/3`，Robot-side Oracle 仍为 `PARTIAL`；Step 7C.3 判定为 `PARTIAL`。不得把 Safety comparison 修复写成 Tomato 抓取成功，也不得把新 PINK failure 与项目 Safety rejection 混为一谈。

当前必须停在 Step 7C.3。未经用户另行明确授权，不得自动修复 PINK/finger current-state 问题，不得增加第 4 次 Oracle trial、重跑 Alphabet/Step 6、运行 Pi0.5 diagnostic rollout、训练、LoRA、RL、Full Fine-Tuning、修改物理/轨迹/success metric 或进行真实机械臂控制。

## 最新阶段边界：Phase 3 / Step 7C.4

Phase 3 / Step 7C.4 已于 2026-08-13 完成纯静态审计。实际 PINK extension 0.1.3 的 Franka configuration/QP 包含 7 个 arm joints 和 2 个 prismatic finger joints；index 8 确认为 `panda_finger_joint2`。失败调用把 Isaac current finger2=`0.04000149667263031 m` 映射到 PINK q[8]，随后在 QP solve 前被 `Configuration.check_limits(tol=1e-6)` 拒绝。该调用没有产生 velocity、integration 或 target。

直接根因是项目把独立控制的 gripper 包含进 arm IK live configuration，使 finger current-state limit check 能阻断整个 arm IK。joint ordering、arm/gripper target merge 和当前 failing-call integration 均已排除；底层 drive tracking overshoot 的具体产生机制仍未记录完整。Step 7C.4=`PASS` 只表示静态根因审计完成，不代表 Tomato 抓取通过。

当前必须停在 Step 7C.4。推荐但尚未执行的下一步是：以项目侧 7D arm-only `controlled_joint_names` 做一次最小修复，并在另行明确授权后只运行一次 `DIAGNOSTIC / NOT COUNTED` Tomato trial。未经授权不得实施该修复、启动 Isaac/Pi0.5、增加 trial、重跑 Step 6、扩大 tolerance、修改 joint limit/physics/trajectory/controller upstream、训练或真实机械臂控制。
## 最新阶段边界：Phase 3 / Step 7C.5

Phase 3 / Step 7C.5 已于 2026-08-13 完成。项目侧将 PINK 从包含 7 arm + 2 prismatic finger 的 9D configuration 改为真正的 7D arm-only configuration；两个 finger 继续由独立 gripper command 和独立 Safety 路径控制。NVIDIA/PINK upstream、joint limits、tolerance、physics、trajectory、controller cost 和 success metric 均未修改。Isaac 启动前 A–H 测试全部通过，包含 Step 7C.3 Safety regression `13/13 PASS`。

按授权只运行了一次 `DIAGNOSTIC / NOT COUNTED` Tomato trial：PINK runtime 为 7D，完整通过 descent step 0~199 和原失败区间 73~74，完成 close/lift/hold；最大/最终竖直位移为 `146.5309/145.8925 mm`，原 finger configuration-limit 错误未再次出现。该结果确认本地 arm/gripper 架构 bug 已修复，因此 Step 7C.5=`PASS`。

历史正式结果仍冻结为 Alphabet `3/3`、Tomato `0/3`、Overall `3/6`。本次 diagnostic 不得计入正式统计，也不能证明 Tomato formal Oracle 已稳健。当前必须停在 Step 7C.5；未经用户新授权，禁止运行第二次 diagnostic、新的 Tomato 3-trial validation、Pi0.5 diagnostic rollout、Step 6、训练、LoRA、RL、修改 physics/trajectory/success metric 或真实机械臂控制。
## 最新阶段边界：Phase 3 / Step 7C.6

Phase 3 / Step 7C.6 已于 2026-08-13 完成。Step 7C.5 修复后的同一 7D arm-only PINK、独立 gripper control 和 Step 7C.3 floating-point-safe Safety，在不修改代码、参数、轨迹、physics 或 success metric 的情况下完成固定 Tomato validation 00/01/02 三次独立 hard-reset 正式试验。运行前后关键代码/配置 SHA-256 完全一致，Safety regression 仍为 `13/13 PASS`。

三次均完成 pre-grasp、200/200 descent、gripper close、lift 和 hold；PINK 均为 `nq=nv=7`，无 finger configuration-limit failure、IK failure 或 Safety violation。三次最大/最终竖直位移均为 `146.5309/145.8925 mm`，高于固定 `60 mm` 阈值。因此 Tomato post-decoupling validation=`3/3 / ROBUST PASS`，basic robot-side scripted Oracle pipeline 当前结论=`ROBUST PASS`。

历史结果必须继续保留：Step 7C Alphabet=`3/3`，original Tomato=`0/3`；Step 7C.3 Tomato post-fix=`0/3`；Step 7C.5 single diagnostic success=`NOT COUNTED`。Step 7C.6 没有使用 Pi0.5，不能证明 Step 6 Pi0.5 `0/3` 是由 robot-side bug 导致，也不代表 Pi0.5 success、LIBERO transfer、跨域泛化或真实机器人部署。

当前必须停在 Step 7C.6。未经用户新授权，禁止运行 Pi0.5 diagnostic rollout、追加 Tomato/Alphabet trial、重跑 Step 6、训练、LoRA、RL、修改 physics/trajectory/success metric 或真实机械臂控制。若获得授权，推荐唯一下一步为 `ONE_POST_STATE_MAPPING_PI05_DIAGNOSTIC_ROLLOUT`。
## 最新阶段边界：Phase 3 / Step 7D

Phase 3 / Step 7D 已于 2026-08-13 完成。严格只运行了一次 `DIAGNOSTIC / NOT COUNTED` Pi0.5 episode：复用 Step 6 fixed initial state 0、相同 2k checkpoint、场景、两路相机、任务、success detector、100-cycle horizon 与 K=1；同时启用此前已确认的 native `tool_center` State Mapping、`[finger1,-finger2]` Gripper Mapping、floating-point-safe Safety、7D arm-only PINK 和独立夹爪。没有新增 orientation 或 timestamp fix。

该回合完成 100 次真实 `predict_action_chunk` 与 100 个执行 cycle，最终 `HORIZON_REACHED`；两物体位移均为 0，未形成 plausible grasp attempt。Safety violation=0、PINK failure=0、finger configuration-limit regression=0、OOM=false。行为变化判定为 `NO_CLEAR_IMPROVEMENT`；Step 7D 的 `PASS` 只表示单次授权诊断完整执行、运行层无关键回归和证据归档，不表示任务成功。

不得把本结果写成新 benchmark 或成功率，不得把 Step 6 的 0/3 仅归因于已修复的 robot-side bug，也不得归因于 Pi0.5/VLM/attention、orientation、timestamp 或 domain gap 的单一内部原因。仍保留 orientation mapping `UNRESOLVED`、历史 image-state skew 最高约 0.15 s、跨模拟器视觉/域差异和 controller/embodiment 差异。

当前决策为 `FREEZE_FRANKA_ISAAC_MAINLINE`。未经用户新的明确授权，禁止运行第二个 Pi0.5 diagnostic episode、state 1/2、追加 Franka benchmark、重跑 Step 6、训练、LoRA、RL、修改 scene/physics/camera/success detector、或真实机械臂控制。建议的后续项目方向仅为人工决定后的 `SO-101 Real Robot Phase`，不得自动开始。

## 最新阶段边界：Phase 3 Closeout / Franka-Isaac Freeze

Phase 3 已于 2026-08-13 正式 closeout，最终工程决策为 `FREEZE_FRANKA_ISAAC_MAINLINE`。本节是当前最新边界，取代前文各 Step 的暂停条件。除非用户明确撤销冻结决定，否则禁止新增 Franka / Isaac rollout、Step 6 重跑、benchmark 刷成功率、orientation/timestamp/action-clipping 深挖、Pi0.5 训练、LoRA、RL 或新 checkpoint。现有 checkpoint、原始结果、视频和日志均为冻结资产，不得覆盖或重新生成。

下一主阶段只记录为 `SO-101_REAL_ROBOT / PLANNED_NOT_STARTED`。没有用户明确授权时，不得创建 SO-101 实验代码、连接或控制硬件、采集数据、训练模型或启动真实机器人闭环。
