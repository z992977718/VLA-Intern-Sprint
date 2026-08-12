# 面试问答

所有回答均受 `notes/final_project_facts.md` 约束。“专业版”用于技术追问，
“小白理解”用于建立直觉，“面试口语版”用于现场简洁作答。

## 1. VLA 是什么？

- **专业版：** VLA（Vision-Language-Action）模型以视觉观察、自然语言指令和机器人状态为条件，直接生成可执行的机器人动作序列，把感知、语言理解和控制连接起来。
- **小白理解：** 它能看场景、听懂任务、知道机械臂当前在哪里，然后决定下一步怎么动。
- **面试口语版：** “VLA 把视觉、语言和动作统一起来。本项目中，Pi0.5 读取两路相机、任务指令和 robot state，再预测机械臂动作。”

## 2. Pi0.5 是什么？

- **专业版：** Pi0.5 是 Physical Intelligence 的 VLA 模型系列。当前 LeRobot 实现使用基于 PaliGemma 的视觉语言组件和 flow-matching action expert 生成连续 action chunk；本项目使用官方实现，没有自行实现模型架构。
- **小白理解：** 它是一个把“看到什么、要做什么”转换成一段机器人运动计划的大模型。
- **面试口语版：** “Pi0.5 是我的主策略模型。我基于 LeRobot 的实现做 continued fine-tuning、闭环评测、性能分析和失败审计，而不是声称自己发明了模型。”

## 3. LeRobot 是什么？

- **专业版：** LeRobot 是 Hugging Face 的机器人学习框架，覆盖数据集、策略配置、训练、采集和评测。本项目所用 Pi0.5 implementation 与 LIBERO integration 均由 LeRobot 提供。
- **小白理解：** 它提供了通用底座，不需要从零重写数据加载器、训练器、策略接口和模拟器适配层。
- **面试口语版：** “LeRobot 提供框架和算法实现；我负责环境复现、实验控制、profiling、闭环评测和证据审计。”

## 4. LIBERO 是什么？

- **专业版：** LIBERO 是面向终身学习与知识迁移的模拟机器人操作 benchmark，基于 MuJoCo/robosuite，包含 Spatial、Object、Goal 和 LIBERO-10 等标准任务套件。
- **小白理解：** 它是一个虚拟桌面实验室，预先定义了机器人、物体、任务、成功规则和初始状态。
- **面试口语版：** “我把 vanilla LIBERO 当作可控的闭环测试环境，不把模拟器结果包装成真实机械臂部署。”

## 5. Observation 是什么？

- **专业版：** Observation 是环境在控制步返回并由 policy 消费的信息。本项目包括两路 RGB 图像和本体状态，语言指令作为任务上下文输入。
- **小白理解：** 它就是机器人此刻的快照：相机看到了什么，以及机械臂自己处于什么状态。
- **面试口语版：** “Policy 看不到模拟器隐藏真值，只能根据两路相机、robot state 和任务指令决定动作。”

## 6. `robot_state` 是什么？

- **专业版：** 当前 Pi0.5 数据 schema 中的 `observation.state` 是 8 维向量，表示末端执行器位置、姿态表示和夹爪状态；LeRobot processor 会把环境中的相关字段映射为 policy feature。
- **小白理解：** 图像告诉模型外部世界，robot state 告诉它自己的机械手在哪里、朝向如何、夹爪是否开合。
- **面试口语版：** “视觉描述外界，robot state 描述机器人自身，两者共同支撑有状态的动作决策。”

## 7. Action 是什么？

- **专业版：** Action 是传给环境的连续控制命令。本项目采用相对末端控制，每个 7 维动作包含六个末端位姿增量和一个夹爪命令。
- **小白理解：** 它是一小步运动指令：手往哪里移动、怎么转、夹爪开还是关。
- **面试口语版：** “Action 不是文本，而是 LIBERO 每个控制步执行的 7 维连续向量。”

## 8. 为什么 action dimension 是 7？

- **专业版：** 三个值表示 3D 平移，三个值表示 3D 旋转，第七个值控制夹爪，因此是 6-DoF 末端运动加 1 个 gripper channel。
- **小白理解：** 三个数移动、三个数转动、一个数开合夹爪。
- **面试口语版：** “7 维就是六自由度末端控制加一维夹爪控制。”

## 9. 什么是 Action Chunk？

- **专业版：** Policy 一次不是只预测一个动作，而是预测一段动作序列。当前 Pi0.5 内部 chunk size 为 50，本评测每次执行其中 10 个动作后重新观察并调用模型，实现周期性闭环重规划。
- **小白理解：** 模型先写一小段运动计划，执行一部分，再看一眼场景并重新规划。
- **面试口语版：** “Pi0.5 一次预测 50 个动作，但我每次只执行 10 个就重新推理，在降低推理频率的同时保留反馈。”

## 10. Fine-tuning 是什么？

- **专业版：** Fine-tuning 是从预训练权重继续优化。本项目从 `pi05_libero_base` 出发，在完整 40 任务 `lerobot/libero` 数据集上继续训练 2,000 steps，不是单任务微调。
- **小白理解：** 不从零训练，而是在已有模型基础上用选定数据继续调整。
- **面试口语版：** “我做的是从 LIBERO base checkpoint 开始的 2,000-step 多任务 continued fine-tuning，并固定了数据 revision。”

## 11. 什么是 expert-only training？

- **专业版：** `train_expert_only=true` 会冻结 VLM，训练 action expert 和投影层。本次 4.143B 总参数中约 693.4M 参数可训练。
- **小白理解：** 大型视觉语言部分保持不动，主要训练负责生成动作的部分。
- **面试口语版：** “Expert-only 用官方配置缩小了可训练范围和显存压力；它不是我私自修改模型结构。”

## 12. 为什么 freeze vision encoder？

- **专业版：** 冻结视觉编码器能减少梯度与 activation memory，并避免短训练阶段扰动视觉表征；代价是对新视觉域的适应能力可能受限。
- **小白理解：** 保持看图骨干不变，让训练更轻量、更保守。
- **面试口语版：** “这是兼顾显存和稳定性的配置，但我也承认它可能限制视觉域适应。”

## 13. Gradient checkpointing 是什么？

- **专业版：** Gradient checkpointing 在 forward 时不保存部分中间激活，backward 时重新计算，以额外计算换取更低 activation memory；它与保存模型 checkpoint 是两个概念。
- **小白理解：** 不记住所有中间结果，需要时重新算一遍，从而节省显存。
- **面试口语版：** “它降低训练显存，代价是增加重算；不要和模型权重 checkpoint 混淆。”

## 14. BF16 有什么作用？

- **专业版：** BF16 以 16 位存储和计算，同时保留接近 FP32 的指数范围，可在支持的 GPU 上降低显存并提升吞吐。本次 2,000 个记录 loss 均为有限值。
- **小白理解：** 用更紧凑的数字表示，让训练更省显存、更快，同时通常能保持较好的数值范围。
- **面试口语版：** “Policy 和 mixed precision 都使用 BF16，最终没有 NaN、Inf 或 OOM。”

## 15. 为什么 loss 下降不代表 robot 成功？

- **专业版：** Training loss 衡量 demonstration batch 上的监督预测误差；Rollout success 还受闭环状态分布、误差累积、接触动力学、恢复能力和成功判定影响。1k/2k 单点 loss 分别约 0.1992/0.2040，但匹配状态成功率从 9/10 到 10/10。
- **小白理解：** 会模仿标准答案，不等于机器人在自己犯小错后还能把任务做完。
- **面试口语版：** “Loss 是离线优化信号，success 是闭环任务结果，所以我不会只看 loss 选结论。”

## 16. Rollout 是什么？

- **专业版：** Rollout 是 policy 反复观察、预测动作、推进环境，并在成功或达到 horizon 时结束的一条轨迹；后续观察由 policy 之前的动作共同造成。
- **小白理解：** 它是机器人从 reset 开始，到成功或超时的一次完整尝试。
- **面试口语版：** “每个 rollout 都是实际闭环 episode，不是静态数据集里的一帧。”

## 17. Closed-loop 和 offline evaluation 有什么区别？

- **专业版：** Offline evaluation 在记录数据上比较预测，不让 policy 改变未来输入；closed-loop 会真正执行动作，因此能暴露误差累积、接触失败和恢复行为。
- **小白理解：** Offline 像做练习册，closed-loop 像真正操作机器人，并承担前面每一步的后果。
- **面试口语版：** “只有闭环 LIBERO rollout 才能暴露错误物体选择和恢复失败，单看 loss 看不到这些。”

## 18. Success rate 怎么计算？

- **专业版：** 在固定协议下，用成功 episode 数除以总 episode 数。成功由 LIBERO 的 `check_success()` 判定，不靠人工看视频；46/50 仅表示重点任务 50 个固定初态中的 46 次成功。
- **小白理解：** 数有多少次完整尝试满足模拟器任务规则，再除以总尝试次数。
- **面试口语版：** “我会同时报告分子、分母、任务和状态集合，不把 46/50 写成 92% LIBERO 总成功率。”

## 19. Pretrained 为什么是 0/10？

- **专业版：** 可确认事实是 `pi05_libero_base` 在该预处理与控制协议下的十个匹配 task-0 episode 全部失败。实验没有隔离出唯一原因；适配程度、轨迹恢复和协议相关行为只能作为可能因素。
- **小白理解：** Base model 没完成这十个特定起点，但仅靠视频不能判断究竟是内部哪个模块导致。
- **面试口语版：** “我把 0/10 当作本协议的实测 baseline，不把它解释成 pretrained 完全没有 LIBERO 能力。”

## 20. 1k 为什么是 9/10？

- **专业版：** 继续训练 1,000 steps 后，十个匹配固定状态中九个成功；state 4 达到 520-step horizon。视频观察到接近目标后的反复接触，但未形成稳定抓取与搬运，内部原因未被仪器化验证。
- **小白理解：** 训练帮助了大多数起点，但一个布局仍让机器人陷入无效重试。
- **面试口语版：** “1k 已达到 9/10，唯一失败表现为抓取/重试问题；我不猜测权重为何恰好形成这种行为。”

## 21. 2k 为什么是 28/30？

- **专业版：** 统一 30-episode 评测覆盖固定状态 0-29，state 14 和 18 失败。前十个状态为 10/10，扩大 initial-state coverage 后才暴露十集测试遗漏的失败。
- **小白理解：** 前十个起点全成功，但测到三十个起点后出现了两个不同布局下的失败。
- **面试口语版：** “2k 的 28/30 来自更广状态覆盖发现的两个 wrong-object-selection failure，说明样本覆盖很重要。”

## 22. 为什么后来变成 46/50？

- **专业版：** 模型没有继续训练。第二次评测覆盖此前未评测的固定 ID 30-49，得到 18/20；与不重叠的 0-29 结果合并后是 `(28+18)/(30+20)=46/50`。
- **小白理解：** 只是多测了二十个起点，十八个成功、两个失败，并不是模型又变好了。
- **面试口语版：** “46/50 是同一个 2k checkpoint 扩大评测覆盖后的结果，不是新 checkpoint 的提升。”

## 23. Initial state 和 seed 是什么关系？

- **专业版：** 在所检查的 wrapper 中，episode seed 会传入环境，但固定 `init_state_id` 通过 `.pruned_init` 独立推进；LIBERO 在 seed/reset 后应用完整 MuJoCo 存储状态。固定 state 0 只改变 seed 时，实测首个 observation 相同。
- **小白理解：** Seed 管随机过程，而这里真正选择桌面与机器人起始配置的是存储的 initial-state row。
- **面试口语版：** “Seed 1030 不会自动等于 state 30；我显式设置 `init_state_id=30`，并逐 episode 记录实际 ID。”

## 24. 为什么不能称 30-49 为真正 unseen state？

- **专业版：** 它们没有出现在此前 0-29 的评测中，但 base checkpoint provenance 与 demonstration metadata 都没有 state-level exposure manifest，无法证明它们未参与训练。准确称呼是 additional evaluation initial states 或 previously unevaluated fixed initial states。
- **小白理解：** 我能证明以前没测过它们，但不能证明训练时从未出现或见过相似状态。
- **面试口语版：** “它们是此前未评测的固定状态，不是被证明 training-held-out 的状态；我已明确纠正这个边界。”

## 25. 为什么没有做 cross-task unseen evaluation？

- **专业版：** 实际 2k 命令使用完整 40 任务数据集且无 task filter，因此这些 suite 内没有对本次 fine-tuning 未见的任务；起始 `pi05_libero_base` 也已有 LIBERO exposure。再选三个任务不满足 unseen-to-fine-tuning 前提。
- **小白理解：** 本轮训练已经用了所有可选任务，不能再从其中挑三个冒充“未见任务”。
- **面试口语版：** “Exposure audit 发现原实验标签无效，所以我没有为了结果而执行 60 个误导性 rollout。”

## 26. Pretrained checkpoint 是否已经接触 LIBERO？

- **专业版：** 当前 LeRobot 文档明确将 `pi05_libero_base` 描述为针对 LIBERO 训练的 checkpoint。数据集级 exposure 可以确认，但没有精确到每个 example 或 initial state 的清单。
- **小白理解：** 它整体上见过 LIBERO，但我们不知道具体见过哪些样本。
- **面试口语版：** “它是 LIBERO base checkpoint，不是完全未接触 LIBERO 的通用模型，因此 unseen claim 必须非常谨慎。”

## 27. 为什么不能声称 open-world generalization？

- **专业版：** 实验使用 vanilla LIBERO、一个深度评测任务、存储固定初态，以及已有 LIBERO exposure 的起始 checkpoint；没有测试新现实环境、真正未见任务、系统性扰动或完整 benchmark。
- **小白理解：** 在一个模拟器任务的多种固定起点表现好，不等于能在任意真实世界工作。
- **面试口语版：** “证据只支持同任务固定初态鲁棒性，不支持开放世界泛化。”

## 28. 四个失败是什么？

- **专业版：** Checkpoint 2k 在固定状态 14、18、41、49 达到 520-step horizon 后失败。四段视频均观察到干扰物选择或放置，其中部分还伴随 clutter collision 和恢复不完整。
- **小白理解：** 四次失败都操作了错误物体，最终没能在时间内把两个目标物都放进篮子。
- **面试口语版：** “共同可观察模式是 wrong-object selection，四个 state ID 和源视频都保留用于审计。”

## 29. 为什么只能说 wrong-object-selection behavior？

- **专业版：** Rollout 视频只能显示外部行为，不能显示内部 attention、语言表示、预测 target ID 或因果干预结果；将其直接归因为 VLM 语义故障会超出当前 instrumentation。
- **小白理解：** 我能看到它拿错了东西，但看不到模型内部到底为什么拿错。
- **面试口语版：** “报告把 observed behavior 和 possible explanation 分开，不把视频症状升级成内部模块诊断。”

## 30. 如果继续下一阶段，你会怎么做？

- **专业版：** 先完成复现与沟通材料；后续应建立真正 held-out 的训练拆分，或做匹配的训练前后 retention matrix，再对语言、相机、布局、光照和噪声进行预先定义指标的单变量扰动实验。
- **小白理解：** 先让“未见”真的未见，再一次只改变一个因素。
- **面试口语版：** “我不会只盲目增加 steps，而会设计有效的 held-out split 或控制变量 robustness matrix。”

## 31. VLA 如何接 ROS 2？

- **专业版：** 后续可由 ROS 2 节点订阅相机、关节/末端状态和任务指令，完成预处理与 policy inference，再将受限动作目标发布给控制接口；模型与执行器之间必须有安全约束、频率控制、生命周期管理、时间同步和急停。
- **小白理解：** ROS 2 把传感器消息送进模型，再把经过检查的动作送向机器人控制器。
- **面试口语版：** “Phase 1 没接 ROS 2。我的设计会把感知推理、安全校验和底层控制拆成清晰节点。”

## 32. VLA 如何部署到真实机械臂？

- **专业版：** 需要对齐相机、state、action semantics，完成标定、机器人动作转换、实时调度、工作空间/碰撞限制和 watchdog，并按离线回放、仿真、低速受保护真机测试逐级验收；闭环自治前必须量化 domain shift 与 latency。
- **小白理解：** 模型输出的七个数不能直接送给电机，必须转换、限幅和安全检查。
- **面试口语版：** “我会从只读采集和离线 replay 开始，再做仿真和低速保护测试，不会从 LIBERO 直接跳到真机运动。”

## 33. 为什么下一阶段考虑 Isaac Sim？

- **专业版：** Isaac Sim 可支持不同机器人资产、更丰富传感器、ROS 2 bridge 和受控 domain randomization，有助于测试工程可迁移性；但它会引入新的物理、渲染和 domain gap，属于新阶段而非当前结果的验证。
- **小白理解：** 它更接近部署工程，但迁移过去本身就是带有新假设的新项目。
- **面试口语版：** “Isaac Sim 适合后续做机器人/ROS 集成和扰动实验，但 Phase 1 没有使用它。”

## 34. Pi0.5 和 SmolVLA 有什么区别？

- **专业版：** 当前源码中的 Pi0.5 使用 PaliGemma `gemma_2b` 变体与 `gemma_300m` action expert，加载后约 4.14B 总参数；LeRobot 文档中的 `smolvla_base` 是约 450M、基于 SmolVLM2 和 action expert 的轻量模型。两者都接收图像/state/语言并生成 action chunk，但规模、backbone、训练 recipe 与硬件权衡不同。
- **小白理解：** Pi0.5 是本项目使用的更大模型，SmolVLA 更轻、更适合低成本实验。
- **面试口语版：** “我选择 Pi0.5 作为主线、SmolVLA 作为可选 baseline；真正比较时必须统一数据和 rollout protocol。”

## 35. 这个项目最大的工程难点是什么？

- **专业版：** 最大难点是贯通环境复现、数据与 checkpoint provenance、fixed-state semantics 和闭环指标的证据链。Exposure audit 改变了实验解释：原先被误认为单任务的运行，实际是 40 任务 continued fine-tuning。
- **小白理解：** 把模型跑起来并非最难，最难的是证明到底训练了什么，以及结果究竟能说明什么。
- **面试口语版：** “我的核心贡献是建立从源码配置、命令、原始结果、视频到 claim boundary 的可审计链路。”

## 36. 你本人到底做了什么，而不是 LeRobot 替你做了什么？

- **专业版：** LeRobot 提供 dataset/policy/training 基础框架、Pi0.5 实现和 LIBERO adapter；我完成环境固定与复现、资产迁移校验、training exposure audit、2k continued fine-tuning 执行、checkpoint 管理、项目侧 profiling/fixed-state wrapper、匹配评测、视频失败分析和复现/表述记录，没有修改上游源码。
- **小白理解：** 我没有发明 Pi0.5；我让官方组件可复现地运行，设计并执行实验，认真测量，并阻止不受证据支持的结论。
- **面试口语版：** “我负责工程实验和证据，不冒领底层算法；README 中已经把 LeRobot 与本项目贡献清楚分开。”
