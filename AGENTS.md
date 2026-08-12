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
