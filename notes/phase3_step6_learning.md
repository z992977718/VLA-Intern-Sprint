# Phase 3 / Step 6 学习笔记

## 1. Episode 是什么？

- 专业解释：从一次环境 reset 开始，到 success、horizon 或安全终止为止的一条完整交互轨迹。
- 小白理解：机器人“从头做一次题”。
- 本项目作用：State 0、1、2 各独立启动 Isaac 进程，互不沿用上一次状态。

## 2. Task 和 Runtime 有什么区别？

- 专业解释：Runtime 验证数据与控制链路能工作；Task 验证目标条件是否真正达成。
- 小白理解：机器能动不等于题做对了。
- 本项目作用：管线 PASS，但 task 是 0/3。

## 3. Success Metric 是什么？

- 专业解释：把环境状态映射为成功/失败的可执行判定规则。
- 小白理解：自动阅卷标准。
- 本项目作用：两个指定罐的中心必须同时位于 basket contain box 内。

## 4. Initial State 是什么？

- 专业解释：episode 开始时机器人、物体和环境的完整状态。
- 小白理解：开局摆法。
- 本项目作用：使用 LIBERO 固定 state 0、1、2 的实测位姿。

## 5. Reset 为什么重要？

- 专业解释：避免前一轨迹的动力学状态污染下一次试验。
- 小白理解：每次考试前都把棋盘重新摆好。
- 本项目作用：三个 episode 都是独立 Isaac 进程 hard reset。

## 6. Horizon 是什么？

- 专业解释：单 episode 允许的最大决策步数。
- 小白理解：最多给机器人多少次尝试。
- 本项目作用：每个 episode 严格最多 100 cycles，不能人为续跑。

## 7. Task Success Rate 是什么？

- 专业解释：成功 episode 数除以总 episode 数。
- 小白理解：三次里做对几次。
- 本项目作用：0/3 = 0%，不能与 pipeline PASS 混淆。

## 8. Domain Gap 是什么？

- 专业解释：训练/评测域在视觉、状态、动作或动力学分布上的差异。
- 小白理解：同一道题换了教室、工具和规则细节。
- 本项目作用：LIBERO 与 Isaac 的 renderer、physics、camera、gripper 都有差异。

## 9. Sim2Sim 是什么？

- 专业解释：策略从一个仿真系统迁移到另一个仿真系统。
- 小白理解：从一个虚拟世界搬到另一个虚拟世界。
- 本项目作用：本实验是 LIBERO → Isaac cross-simulator evaluation。

## 10. Sim2Real 和 Sim2Sim 的区别？

- 专业解释：Sim2Real 的目标域是真实硬件；Sim2Sim 的两端都是仿真。
- 小白理解：虚拟到真实，与虚拟到另一个虚拟，不是一回事。
- 本项目作用：没有真实机械臂，因此不能称 sim-to-real。

## 11. 为什么 LIBERO → Isaac 也存在迁移问题？

- 专业解释：仿真器之间仍有 renderer、contact solver、资产和控制接口差异。
- 小白理解：两个游戏引擎画面和物理手感也不一样。
- 本项目作用：相同任务语义没有保证直接成功。

## 12. 为什么同一个 Franka 也不能保证 policy 成功？

- 专业解释：机器人名称相同不代表关节、工具点、夹爪、相机、控制器和动力学分布相同。
- 小白理解：同型号车换了摄像头、轮胎和路面，驾驶感仍会变。
- 本项目作用：需要 EEF offset、gripper 和 PINK 映射。

## 13. Distribution Shift 是什么？

- 专业解释：部署输入/状态分布偏离训练时分布。
- 小白理解：训练时没见过这种画面或手感。
- 本项目作用：Isaac observation 与 LIBERO observation 有可见差异。

## 14. 为什么 Failure Analysis 比单个成功视频更重要？

- 专业解释：完整失败分布能揭示系统性问题并避免 cherry-picking。
- 小白理解：只展示一次好运不能说明稳定。
- 本项目作用：完整保留 3 个 100-cycle 失败视频和 300 轮日志。

## 15. 为什么不能称 unseen-task generalization？

- 专业解释：该指令属于完整 40-task LIBERO continued fine-tuning 数据；变化的是 simulator，不是任务语义暴露。
- 小白理解：题目以前学过，只是换了考试环境。
- 本项目作用：允许称 cross-simulator/domain transfer，禁止称 unseen-task 或 zero-shot new-task。
