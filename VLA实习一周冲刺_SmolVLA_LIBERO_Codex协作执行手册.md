# VLA 实习一周冲刺：SmolVLA + LIBERO + Codex 协作执行手册

> **目标不是秋招最终项目。**
>
> 这一周的目标是：在没有机械臂真机的情况下，用仿真真正跑通一次  
> **VLA 数据理解 → 模型微调 → Checkpoint → 仿真闭环 Rollout → 评测 → 失败分析**，
> 并让自己能够在实习面试中清楚解释整个链路。
>
> 技术路线：
>
> **LeRobot + SmolVLA + LIBERO + GPU Server + Codex**

---

# 0. 一周结束时必须拿到的成果

```text
1. LeRobot + LIBERO 环境正常运行
2. 能解释 Observation / Language / Action
3. 能加载并检查 LeRobot 格式 LIBERO 数据
4. 真正运行一次 SmolVLA Fine-tuning
5. 得到自己的 Checkpoint
6. 自己的 Checkpoint 回到 LIBERO 做闭环 Rollout
7. 记录 Success / Failure / Latency
8. README + 日志 + 面试回答
```

简历最终只写真实完成的内容：

> **基于 LeRobot 与 LIBERO 搭建 VLA 机器人操作训练评测环境，使用 SmolVLA 对机器人示范数据进行微调，并将微调 Checkpoint 部署至 LIBERO 仿真机械臂进行闭环 Rollout，完成任务成功率、推理性能及典型失败案例分析。**

注意：

> **这是“仿真闭环部署”，不是“真机部署”。**

---

# 1. 一张图看懂整个项目

```text
Natural Language
"pick up ..."

        +

Camera Observation
RGB / Wrist Camera

        +

Robot State
EEF / Joint / Gripper State

        ↓

      SmolVLA

        ↓

    Action Chunk

        ↓

LIBERO Controller

        ↓

Simulation Robot

        ↓

New Observation

        ↓

再次进入 SmolVLA
```

这叫：

> **Closed-loop Policy Rollout**

和普通图像分类最大的区别：

```text
普通模型：
Input → Prediction → 结束

机器人 Policy：
Observation → Action → 环境改变
            ↑              ↓
            └── 新 Observation
```

---

# 2. 为什么选 SmolVLA + LIBERO

## SmolVLA

SmolVLA 是 Hugging Face LeRobot 官方提供的轻量 VLA。

当前官方文档说明其输入包括：

```text
多个 Camera View
+
Robot Sensorimotor State
+
Natural Language Instruction
```

输出：

```text
Action Chunk
```

基础模型约 **450M 参数**，适合在 LeRobot 数据集上微调。

对于只有一周的实习冲刺，比直接上大型 VLA 更合适。

## LIBERO

LIBERO 是机器人 manipulation 学习 Benchmark，LeRobot 当前已经提供统一的：

```text
Dataset
Training
Evaluation
```

接口。

本周不要自己搭 Isaac Sim 场景。

因为本周目标是：

> **快速理解 VLA 的数据—训练—执行—评测闭环，而不是花时间搭仿真资产。**

---

# 3. 电脑分工

推荐：

```text
轻薄本
│
├── ChatGPT
├── Codex Desktop
├── VS Code
├── Git
├── Markdown / README
└── SSH
       │
       ↓
GPU Server（Linux）
│
├── LeRobot
├── LIBERO
├── PyTorch
├── SmolVLA
├── MuJoCo
├── Dataset
├── Fine-tuning
└── Evaluation
```

轻薄本主要负责：

```text
写代码
看代码
写README
Git
面试准备
```

GPU Server 主要负责：

```text
CUDA
数据加载
训练
仿真
评测
Checkpoint
```

---

# 4. ChatGPT 和 Codex 怎么分工

## ChatGPT：老师 + 架构师 + 面试官

适合问：

```text
这个概念是什么意思？
为什么这么设计？
VLA和BC是什么关系？
Action Chunk为什么存在？
这个结果能不能写进简历？
面试官会怎么追问？
```

## Codex：仓库级工程助手

适合：

```text
读 LeRobot 源码
检查 API
搭环境
运行命令
分析错误日志
写辅助脚本
整理评测结果
更新 README
```

原则：

> **不要让 Codex 替你“做项目”，让它替你提高工程执行速度。**

---

# 5. Codex 项目目录

建议建立：

```text
VLA-Intern-Sprint/
│
├── AGENTS.md
├── README.md
│
├── notes/
│   ├── daily_log.md
│   ├── concepts.md
│   ├── commands.md
│   ├── project_facts.md
│   └── interview.md
│
├── scripts/
│   ├── inspect_dataset.py
│   ├── inspect_checkpoint.py
│   ├── profile_policy.py
│   └── summarize_eval.py
│
├── results/
│   ├── training/
│   ├── evaluation/
│   └── failure_cases/
│
└── lerobot/
    └── 官方仓库
```

`lerobot/` 尽量保持官方代码原样。

自己新增的内容优先放：

```text
scripts/
notes/
results/
```

---

# 6. 第一次打开 Codex

在 Codex Desktop：

```text
Add project
↓
选择 VLA-Intern-Sprint
```

然后运行：

```text
/init
```

生成 `AGENTS.md`。

OpenAI 官方建议使用 `AGENTS.md` 给 Codex 提供持续的项目上下文、仓库规则和测试说明。

---

# 7. 推荐 AGENTS.md

```markdown
# 项目目标

这是一个为期 7 天的实习准备项目。

目标：使用 LeRobot + SmolVLA 微调 VLA policy，并在 LIBERO 模拟 benchmark 中进行评测。

这不是真实机器人项目。

# 主要约束

1. 不得声称真实机器人部署。
2. 优先使用 LeRobot/LIBERO 官方 API。
3. 不得静默修改 package version。
4. 修改上游 `lerobot/` 前先解释原因。
5. 优先在 `scripts/` 下添加轻量脚本。
6. 将重要命令记录到 `notes/commands.md`。
7. 记录环境版本和 Git commit hash。
8. README 指标必须来自真实日志。
9. 不得编造成功率、延迟或硬件结果。
10. 解释应对初学者友好，同时保持技术准确。

# 工作流程

每项任务：
1. 先检查代码和文档。
2. 解释发现。
3. 提出最小改动。
4. 执行并测试。
5. 报告准确结果。
6. 按需更新笔记。

# 项目产物

- README.md
- notes/concepts.md
- notes/daily_log.md
- notes/project_facts.md
- scripts/
- results/
```

---

# 8. 给 Codex 下任务的模板

不要说：

> 帮我把 SmolVLA + LIBERO 全部做完。

而要写成类似 GitHub Issue：

```text
背景：
...

目标：
...

限制：
...

请先检查：
...

验收标准：
...

禁止：
...
```

例如：

```text
背景：
我在做一个7天VLA实习准备项目，使用LeRobot、SmolVLA、LIBERO。

目标：
确认当前仓库版本下，LIBERO + SmolVLA训练所需的正确安装方式。

限制：
不要修改任何代码。
不要凭记忆回答，必须读取当前仓库的pyproject.toml和相关docs。

请：
1. 检查Python要求；
2. 检查smolvla/libero/training extras；
3. 给出最小安装命令；
4. 给出安装后的验证命令；
5. 把最终成功命令写入notes/commands.md。

验收：
python能import torch、lerobot、libero；
CUDA可用；
能初始化一个LIBERO环境。
```

---

# 9. Day 1：环境 + 版本固定

## 今日目标

今天不训练。

只完成：

```text
Python
PyTorch
CUDA
LeRobot
LIBERO
MuJoCo
SmolVLA dependencies
```

## Step 1：检查服务器

```bash
nvidia-smi
python --version
```

记录：

```text
GPU型号
显存
Driver
CUDA
OS
```

## Step 2：建立环境

当前 LeRobot 官方安装文档推荐 Python 3.12：

```bash
conda create -y -n vla-sprint python=3.12
conda activate vla-sprint
conda install ffmpeg -c conda-forge
```

## Step 3：Clone LeRobot

```bash
git clone https://github.com/huggingface/lerobot.git
cd lerobot
git rev-parse HEAD
git status
```

把 commit hash 记录下来。

LeRobot 更新很快，因此不要只说：

> “我用的是 LeRobot。”

要知道：

> “我基于哪个 commit / 环境完成的实验。”

## Step 4：安装

先让 Codex 读取当前：

```text
pyproject.toml
docs
```

确认 extras。

当前官方文档对应功能包括：

```text
training
smolvla
libero
```

如果当前源码支持组合安装：

```bash
pip install -e ".[training,smolvla,libero]"
```

若组合安装出现问题，则分别：

```bash
pip install -e ".[training]"
pip install -e ".[smolvla]"
pip install -e ".[libero]"
```

## Step 5：Headless Server

当前 LeRobot LIBERO 文档要求 Linux。

Headless GPU Server：

```bash
export MUJOCO_GL=egl
```

## Step 6：验证 CUDA

```bash
python - <<'PY'
import torch
print("torch:", torch.__version__)
print("cuda available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0))
PY
```

## 第 1 天 Codex 提示词

```text
今天只做环境验证，不做训练。

请先读取当前仓库：
- pyproject.toml
- installation docs
- LIBERO docs
- SmolVLA docs

然后：
1. 检查当前Python/PyTorch/CUDA要求；
2. 检查training/smolvla/libero extras；
3. 检查服务器环境；
4. 给最小安装方案；
5. 执行验证；
6. 不要为了消除错误随意改核心版本；
7. 版本冲突先解释再处理；
8. 成功命令记录到notes/commands.md；
9. GPU、Python、Torch、CUDA、LeRobot commit记录到notes/daily_log.md。

验收：
- import torch成功
- CUDA可用
- import lerobot成功
- import libero成功
- 能初始化LIBERO环境
```

---

# 10. Day 2：数据和环境

今日目标：

> **亲眼看到 VLA 的输入和输出。**

## Step 1：检查 LIBERO Task

让 Codex 找到当前版本中的：

```text
task suite
task id
language instruction
observation keys
action space
control mode
```

当前 LeRobot LIBERO 文档中，典型观察包含：

```text
Robot State
Main Camera
Wrist Camera
```

Action 为连续控制量。

不同 policy 可能使用：

```text
relative
absolute
```

控制方式，必须和训练时的 Action Parameterization 对齐。

## Step 2：写 inspect_dataset.py

任务：

> 加载 `HuggingFaceVLA/libero`，只检查少量 sample。

希望输出：

```text
Dataset length
Episode count
Task / Task index
Episode index
Observation keys
Image shape
State shape
Action shape
Timestamp
```

## 第 2 天 Codex 提示词

```text
任务：理解当前LeRobot版本中的LIBERO训练数据。

先不要训练。

请：
1. 阅读LeRobotDataset API；
2. 检查HuggingFaceVLA/libero的数据字段；
3. 创建scripts/inspect_dataset.py；
4. 只读取少量sample；
5. 打印task、episode、observation、image、state、action等信息；
6. 用注释解释字段在机器人学习中的意义；
7. 把结论写入notes/concepts.md。

不要：
- 修改官方dataset；
- 全量遍历无关数据；
- 猜字段含义。
```

## 今天必须搞懂

```text
Episode
Trajectory
Observation
Robot State
Action
Language Instruction
Action Chunk
```

---

# 11. Day 2 可选：LIBERO Evaluation Smoke Test

如果服务器和时间允许，可用 LeRobot 官方示例中的已微调 LIBERO policy 做一次环境验证：

```bash
lerobot-eval   --policy.path=lerobot/pi0_libero_finetuned   --env.type=libero   --env.task=libero_object   --eval.n_episodes=10
```

目的只是确认：

```text
Policy
↓
LeRobot Eval
↓
LIBERO
↓
Robot Action
```

可以跑。

如果 Pi0 依赖安装很慢：

> **直接跳过。**

不要让可选步骤吃掉一天。

---

# 12. Day 3：SmolVLA 训练 Smoke Test

今天第一次训练，但不追求效果。

目标：

```text
Dataset
↓
Dataloader
↓
SmolVLA
↓
Forward
↓
Loss
↓
Backward
↓
Optimizer
↓
Checkpoint
```

全部跑通。

当前 LeRobot LIBERO 官方训练形式类似：

```bash
lerobot-train   --policy.type=smolvla   --policy.repo_id=${HF_USER}/libero-test   --policy.load_vlm_weights=true   --dataset.repo_id=HuggingFaceVLA/libero   --env.type=libero   --env.task=libero_10   --output_dir=./outputs/   --steps=100000   --batch_size=4   --eval.batch_size=1   --eval.n_episodes=1   --env_eval_freq=1000
```

但本周不要直接跑 100k。

先：

```bash
lerobot-train --help
```

确认当前版本参数，然后只做：

```text
50~100 steps
```

Smoke Test。

## 第 3 天 Codex 提示词

```text
任务：做SmolVLA + LIBERO最小训练Smoke Test。

要求：
1. 先运行lerobot-train --help确认当前参数；
2. 参考当前官方LIBERO配置；
3. 先50~100 step；
4. batch size从保守值开始；
5. 记录GPU显存、step time、loss、checkpoint；
6. OOM时先分析，再减batch；
7. 不随机改版本；
8. 成功命令写入notes/commands.md；
9. 日志放results/training/smoke_test/。

验收：
训练完成若干step；
loss是有限值；
生成可加载checkpoint。
```

今天必须会回答：

### Fine-tuning 是什么？

> 在预训练 VLA 基础上，用目标机器人/任务 demonstration 数据继续优化，让模型适应目标 observation、action distribution 和任务。

### Loss 是什么？

> 用来度量模型预测和训练目标之间的差异；具体损失形式以当前 SmolVLA 实现为准，不没看代码就乱背公式。

---

# 13. Day 4：正式短 Fine-tuning

今天开始产生真正项目结果。

## 训练规模

按服务器和时间决定：

```text
2k
5k
10k steps
```

不追 SOTA。

核心是：

```text
训练完整结束
+
保存自己的Checkpoint
+
后面真正拿它Rollout
```

至少记录：

```text
Training Loss
Learning Rate
Step
GPU Memory
Step Time
Checkpoint
```

保存环境：

```bash
git rev-parse HEAD
pip freeze > ../notes/pip-freeze.txt
nvidia-smi
```

## 第 4 天 Codex 提示词

```text
任务：正式运行短程SmolVLA LIBERO fine-tuning。

前提：
Smoke Test已成功。

请：
1. 根据昨天显存和step time估算今天能完成的训练规模；
2. 说明batch size和steps原因；
3. 启动训练；
4. 明确输出目录；
5. 保存checkpoint；
6. 从真实日志提取initial/final loss、steps、elapsed time、GPU信息；
7. 生成results/training/training_summary.md；
8. 不要因为loss下降就宣称robot task成功。
```

记住：

> **Loss 下降 ≠ Closed-loop Rollout 成功。**

---

# 14. Day 5：自己的 Checkpoint 做闭环 Rollout

这是本周最重要的一天。

今天完成以后，才能说：

> **“我把微调模型部署回仿真机器人环境进行了闭环执行。”**

## Step 1：找到 Checkpoint

不同 LeRobot 版本目录可能变化。

不要猜。

让 Codex：

```text
检查实际output_dir
找到lerobot-eval可加载的checkpoint
验证policy config
```

## Step 2：只测一个 Suite + 一个 Task

先：

```bash
lerobot-eval --help
```

再按当前版本执行类似：

```bash
lerobot-eval   --policy.path="<YOUR_CHECKPOINT>"   --env.type=libero   --env.task=libero_object   --env.task_ids='[0]'   --eval.batch_size=1   --eval.n_episodes=5   --env.max_parallel_tasks=1
```

先检查：

```text
Checkpoint能不能加载？
Observation key匹配吗？
Action shape匹配吗？
Control mode匹配吗？
机器人会动吗？
Episode正常结束吗？
```

## 第 5 天 Codex 提示词

```text
任务：把昨天得到的SmolVLA checkpoint部署到LIBERO做闭环rollout。

请：
1. 找到实际checkpoint路径；
2. 运行lerobot-eval --help；
3. 先选择libero_object一个task；
4. 只跑少量episode；
5. 检查policy加载、observation、action shape、control mode、episode结束；
6. 保存实际评测输出；
7. 统计success/failure；
8. 写results/evaluation/eval_summary.md。

禁止：
- 篡改失败结果；
- 把官方模型结果算成我的结果；
- 把仿真写成真机。
```

---

# 15. 必须掌握：Action Parameterization

LIBERO 的 Action 不是：

> “抓杯子。”

而是连续控制量。

当前 LeRobot LIBERO 支持不同 control mode，例如：

```text
relative
absolute
```

必须理解：

> **模型训练时的 Action Representation 必须与执行端对 Action 的解释一致。**

例如：

```text
模型输出的是增量
Controller却当绝对位置
```

机器人行为一定错误。

这就是非常典型的 VLA Deployment 接口问题。

---

# 16. Day 6：Latency + Failure Analysis

今天不要继续无限调成功率。

开始增加工程味。

## Part A：Latency

创建：

```text
scripts/profile_policy.py
```

让 Codex 先找到当前版本：

```text
Policy加载入口
Observation Processor
实际Action inference位置
Action Postprocess
```

然后做最薄的 wrapper，不修改核心代码。

至少记录：

```text
Inference mean
P50
P95
GPU型号
Batch size
```

若容易实现，再拆：

```text
Preprocess
↓
Policy inference
↓
Postprocess
```

## Profiling Codex 提示词

```text
任务：为当前SmolVLA checkpoint写最小推理profiling脚本。

先：
1. 查当前Policy API；
2. 找实际Action inference的位置；
3. 不修改upstream核心代码。

创建scripts/profile_policy.py：
- 加载我的checkpoint；
- 使用真实LIBERO sample/env observation；
- warmup；
- 多次正式测量；
- CUDA计时注意synchronize；
- 输出mean/p50/p95；
- 记录GPU和batch size；
- 保存results/evaluation/latency.json。

不要：
- 混淆CPU wall time和GPU kernel time；
- 伪造数据。
```

---

# 17. Failure Analysis

从评测中挑：

```text
Success × 1~2
Failure × 2~3
```

每个失败案例记录：

```text
任务：
现象：
失败发生在哪一步：
能看到的证据：
可能原因：
下一步怎么验证：
```

注意把：

```text
事实
```

和：

```text
推测
```

分开。

## 失败分析 Codex 提示词

```text
读取evaluation日志和实际rollout输出。

请：
1. 列出真实失败episode；
2. 根据能观察到的现象分类；
3. 每类失败区分：
   - 事实
   - 假设
   - 还需要什么实验验证
4. 写results/failure_cases/failure_analysis.md。

不要把没有证据的原因写成确定结论。
```

---

# 18. Day 7：停止加功能，变成面试项目

今天不再开新坑。

## README 结构

```text
1. Project Motivation
2. Architecture
3. Environment
4. Dataset
5. SmolVLA
6. Fine-tuning
7. Simulation Rollout
8. Evaluation
9. Failure Analysis
10. Limitations
11. Next Step
```

架构图：

```text
LIBERO Dataset
      │
      ↓
Observation
├── Camera
├── State
└── Language
      │
      ↓
SmolVLA Base
      │
  Fine-tuning
      │
      ↓
My Checkpoint
      │
      ↓
LIBERO Environment
      │
      ↓
Action Chunk
      │
      ↓
Robot Controller
      │
      ↓
Closed-loop Rollout
      │
      ↓
Success / Failure / Latency
```

## README Codex 提示词

```text
根据当前仓库的真实代码、命令和results生成README。

规则：
1. 所有数字来自真实日志；
2. 没完成的写Future Work；
3. 明确写Simulation，不写Real Robot；
4. 官方baseline不能算我的成绩；
5. 讲清dataset → fine-tuning → checkpoint → rollout → evaluation；
6. 加Known Limitations；
7. 技术细节足够面试追问。
```

---

# 19. 最后生成 project_facts.md

让 Codex 只根据真实仓库回答：

```text
1. 实际用了什么模型？
2. Dataset是什么？
3. Observation包含什么？
4. Action是什么？
5. Fine-tuning命令是什么？
6. 训练多少step？
7. GPU是什么？
8. Rollout多少次？
9. Success rate多少？
10. Latency多少？
11. 失败案例是什么？
12. 哪些还没有做？
```

保存：

```text
notes/project_facts.md
```

然后把这个文件发给 ChatGPT。

再把真实事实转换成：

```text
专业版面试回答
+
小白版解释
+
追问
```

这样可以避免 AI 帮你“包装过头”。

---

# 20. 一周执行表

| Day | 上午 | 下午/晚上 | 验收 |
|---|---|---|---|
| 1 | Server/CUDA | LeRobot+LIBERO | 环境跑通 |
| 2 | LIBERO环境 | Dataset Inspector | 看懂Obs/Action |
| 3 | SmolVLA API | 50~100 step Smoke | 训练链跑通 |
| 4 | 正式Fine-tune | Checkpoint | 有自己的模型 |
| 5 | 单Task Eval | Closed-loop Rollout | Robot执行 |
| 6 | Profiling | Failure Analysis | 有工程分析 |
| 7 | README | 面试事实/问答 | 可投递版本 |

---

# 21. 每天开始前给 Codex 的固定 Prompt

```text
先检查当前项目状态，不修改代码。

告诉我：
1. 昨天完成了什么；
2. 今天唯一目标是什么；
3. 当前最大风险是什么；
4. 今天最小可验证里程碑是什么；
5. 哪些事情今天明确不做。
```

---

# 22. Debug 的错误方式

不要：

```text
报错
↓
AI让我pip install xxx
↓
又报错
↓
升级yyy
↓
降级torch
↓
环境炸掉
```

---

# 23. Debug 的正确 Prompt

```text
先不要修改环境。

请：
1. 读取完整错误堆栈；
2. 找第一个真正有效的异常；
3. 检查当前package版本；
4. 检查当前仓库dependency声明；
5. 判断属于：
   - API变化
   - 缺依赖
   - 版本冲突
   - CUDA
   - MuJoCo
   - Dataset
   - 参数错误
6. 解释根因；
7. 给最小修复；
8. 修复后只做最小验证。
```

---

# 24. 每次成功都留下证据

不是：

> “我记得成功过。”

而是：

```text
Command
+
Log
+
Config
+
Checkpoint
+
Result
```

每完成一步：

```text
notes/commands.md
results/
git commit
```

---

# 25. 推荐 Git 节奏

```text
Day 1
chore: set up lerobot libero environment

Day 2
feat: add libero dataset inspector

Day 3
exp: run smolvla training smoke test

Day 4
exp: fine tune smolvla on libero

Day 5
eval: run closed loop libero evaluation

Day 6
feat: add policy profiling and failure analysis

Day 7
docs: finalize internship sprint report
```

---

# 26. 面试最可能追问的 12 个问题

## 1. 为什么用 SmolVLA？

```text
轻量
预训练VLA
LeRobot原生支持
适合快速跑通Fine-tuning与Rollout
本项目目标是完整Pipeline而不是SOTA
```

## 2. VLA 输入是什么？

```text
Vision
+
Language
+
Robot State
```

## 3. 输出是什么？

```text
Robot Action / Action Chunk
```

不是文本。

## 4. Fine-tuning 本质是什么？

```text
Pretrained Policy
+
Robot Demonstration
↓
适应目标任务Observation/Action分布
```

## 5. Demonstration Data 是什么？

```text
Observation → Expert Action
```

组成的轨迹。

## 6. Action Chunk 是什么？

一次预测未来一段连续动作，而不是只预测一个瞬时动作。

## 7. Rollout 是什么？

```text
Observation
↓
Policy
↓
Action
↓
Environment
↓
New Observation
```

循环执行。

## 8. Loss 下降为什么不代表机器人成功？

因为：

```text
Offline prediction
≠
Closed-loop execution
```

模型自己的动作会改变后续 Observation。

## 9. Distribution Shift 怎么产生？

训练时大多看到专家轨迹。

部署时 policy 自己的小错误会把机器人带到训练数据里没见过的状态。

## 10. LIBERO 为什么适合本项目？

因为它提供：

```text
Manipulation Tasks
Demonstrations
Language
Simulation
Evaluation
```

可以快速验证 VLA 完整闭环。

## 11. 项目不足是什么？

> 当前完成的是仿真中的 Fine-tuning 和闭环评测，不是真机。真机还会增加标定、控制接口、延迟、安全、硬件误差和 Sim2Real 等问题。

## 12. 下一步是什么？

```text
LIBERO Simulation
↓
真实机械臂 Dataset
↓
VLA Fine-tuning
↓
Real Robot Rollout
↓
ROS2 Runtime
↓
Action Adapter
↓
Safety / Watchdog
↓
Latency / Failure Logger
```

---

# 27. 最终面试介绍模板

> 我之前的主要积累是 C++ / ROS2 和机器人系统。为了快速补齐 VLA 方向，我基于 LeRobot 和 LIBERO 跑通了 SmolVLA 的数据理解、Fine-tuning、Checkpoint 加载以及仿真机械臂闭环 Rollout，并进一步做了任务成功情况、推理延迟和失败案例分析。这个过程让我实际理解了从视觉、语言和 Robot State 到 Action Chunk 的 VLA pipeline。目前完成的是仿真闭环验证，我没有把它包装成真机经验；真机侧的控制接口、安全和 Sim2Real 是下一阶段继续补的内容。

---

# 28. 当前官方资料依据

本计划按 **2026-08-10** 核对的官方资料设计：

```text
Hugging Face LeRobot
- Installation
- SmolVLA
- LIBERO Integration
- LeRobot GitHub README

LIBERO
- Official GitHub Repository

OpenAI
- Get started with Codex
- ChatGPT Work and Codex
- How OpenAI uses Codex
- Introducing Codex / AGENTS.md
```

当前官方资料支持的关键事实：

```text
LeRobot当前安装文档推荐Python 3.12环境；
SmolVLA基础模型约450M；
SmolVLA输入多相机、机器人状态和语言，并生成Action Chunk；
LeRobot提供LIBERO统一training/evaluation接口；
LIBERO的LeRobot集成要求Linux；
Headless server可设置MUJOCO_GL=egl；
Codex可以处理本地文件夹/Git仓库；
AGENTS.md可用于给Codex提供持久项目规则和上下文。
```

---

# 29. 最后的原则

这一周不是比：

> “谁懂的 VLA 论文更多。”

而是在证明：

```text
给我一个陌生机器人AI技术栈
↓
我能读文档
↓
能搭环境
↓
能读源码
↓
能理解数据
↓
能训练
↓
能Rollout
↓
能评测
↓
能Debug
↓
能把结果说清楚
```

对于实习面试，这就是非常有价值的学习能力证明。
