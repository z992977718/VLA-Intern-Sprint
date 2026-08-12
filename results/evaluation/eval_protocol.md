# Pi0.5 第一阶段评测协议

## 范围

这是本项目第一次闭环实验。它在一个具有代表性的 LIBERO-Long 任务上做配对比较，不是完整的 400-episode LIBERO benchmark。两个 policy 必须使用完全相同的任务、initial-state 处理、seed、Observation 设置、动作执行 horizon、episode limit 和精度。

## 固定协议

| 项目 | 数值 |
| --- | --- |
| LeRobot | `0.6.2`，commit `22bd7a2f489b367d8df42de803b1e8c4ca63a3f9` |
| 环境 | LIBERO；无界面 MuJoCo，`MUJOCO_GL=egl` |
| Suite / task | `libero_10`，task ID `0` |
| 任务语言 | `put both the alphabet soup and the tomato sauce in the basket` |
| Baseline checkpoint | `/root/autodl-tmp/cache/huggingface/pi05_libero_base` |
| Fine-tuned checkpoint | 第一阶段 `002000/pretrained_model` |
| Observation | 两路 RGB 相机 + 8 维 robot state；LIBERO wrapper 默认 `360x360`，policy resize 为 `224x224` |
| Action | 7 维相对末端增量 + gripper，范围 `[-1, 1]` |
| Action chunk 执行 | 官方 Pi0.5 LIBERO recipe 的 `n_action_steps=10` |
| Episode limit | 520 control steps，即当前源码对 `libero_10` 的默认值 |
| Initial states | 启用 LIBERO 固定 initial states；启用 hard reset |
| 正式 episodes | 每个 checkpoint 10 个 |
| 正式 seeds | `1000` 到 `1009` |
| Pipeline smoke | 单独使用 seed `999` 运行一个 baseline episode，不计入对比 |
| Evaluation batch size | 1；episodes 顺序运行 |
| Success | LIBERO 环境 `check_success()` 的结果 |
| 视频 | 全部 10 个正式 episodes，以环境 FPS（20 Hz）输出 MP4 |
| 精度 | Policy 参数和推理均为 `bfloat16`；`use_amp=false` |
| 设备 | RTX 6000D 上的 `cuda` |

## 延迟定义

Pi0.5 预测 50-step action chunk，本协议执行其中 10 个动作后再调用模型。Profiling wrapper 对每次真实 `predict_action_chunk` 调用计时，并在调用前后立即执行 CUDA synchronization。因此 `latency.csv` 测量的是模型推理调用，而不是两次推理之间九次几乎无成本的 deque 取动作。

每个 episode 的 Rollout wall time 和 episode length 单独记录。延迟按全部模型调用计算 mean、median 和 p95。第一次调用被保留，因为模型 warm-up 也是观察到的部署成本；原始表格允许重新计算 warm 和 steady-state 数值。

## 输出约定

每个评测目录包含：

- `config.json`：解析后的协议和 policy 设置；
- `eval_info.json`：LeRobot 官方逐 episode 与聚合输出；
- `summary.json`：硬件、成功率、计时、延迟和 CUDA memory 汇总；
- `episodes.csv`：每个 episode 一行，包含 seed、success、length 和 latency；
- `latency.csv`：每次模型推理调用一行；
- `eval.log`：完整 stdout/stderr；
- `nvidia_smi_before.txt` 与 `nvidia_smi_after.txt`；
- `videos/`：渲染后的 Rollout 视频；
- `failure_cases.md`：具体失败 episode 清单。

## 解释边界

十个配对 episode 的结果只支持该任务的第一阶段工程决策，不能报告成完整 LIBERO 分数。Training loss 与 closed-loop success 是不同测量值；loss 更低本身不能证明 policy 更好。
