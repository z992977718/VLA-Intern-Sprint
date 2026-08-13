# 项目事实

## 当前阶段

```text
Phase 1: π0.5 + LeRobot + LIBERO — DONE
Phase 2: Isaac Sim + ROS 2 + Manipulator Deployment — IN PROGRESS
```

- Phase 1 已冻结：不得修改实验结果、重新训练 Pi0.5、启动 LIBERO Rollout，或删除 checkpoint/原始实验数据。
- Phase 2 / Step 1 的唯一运行目标是建立 ROS 2 joint command → Isaac Sim Franka articulation → ROS 2 joint-state feedback 的最小闭环；禁止接入 Pi0.5、Camera、MoveIt 或抓取。
- Phase 2 / Step 1 已于 2026-08-12 通过：Isaac Sim 6.0.1、ROS 2 Humble、官方 Franka Panda、physics、ROS 2 Bridge、`/joint_command` 与 `/joint_states` 均完成真实闭环验证。
- Step 1 PASS 只覆盖 application/physics/ROS 2 关节闭环，不覆盖 RTX 图像渲染。Step 2 首次运行曾因 GLX ICD 出现 Vulkan `ERROR_INCOMPATIBLE_DRIVER`；通过新增指向 `libEGL_nvidia.so.0` 的 headless ICD 后，`vulkaninfo` 与 Isaac RTX Camera 均已通过。
- Phase 2 / Step 2 最终 Attempt 007 为 PASS：external RGB、wrist tracking RGB 与 `/joint_states` 均真实发布，Observation Adapter 退出码 0，必需文件无缺失，峰值显存 3265 MiB，无 OOM。
- 两路图像均为 256×256 `rgb8`。外部相机与第二路跟随视角暗像素占比分别为 0.182% 和 0.116%；图像与 joint state 最大时间戳差为 0.05 秒。
- 第二路是 `/World/WristTrackingCamera` 虚拟跟随视角：每帧随 `panda_hand` 世界位置平移并注视前下方工作区；它不是已标定的刚性 eye-in-hand 实体相机外参。
- Step 2 只建立 Observation 数据链路；`policy_loaded=false`、`vla_action_sent=false`，没有执行 Pi0.5 inference、控制、抓取或 Step 3。
- 最终一键复现的 Franka 七轴初始/目标/结果分别为 `[0.012,-0.5686,0,-2.8109,0,3.0368,0.741]`、`[0,-0.45,0,-1.75,0,1.3,0.78]`、`[0.0001,-0.4489,0,-1.7715,0,1.3560,0.7796]`，最大误差 0.0560 rad。
- Step 1 RTX 场景 peak GPU VRAM 实测为 577 MiB，OOM=NO；该值不外推到 Camera、VLA 或更复杂场景。
- Remote visualization 为 NOT CONFIGURED；这不影响已由关节数值证据验证的 headless 仿真执行。

- 当前主要 VLA 模型是 Pi0.5；SmolVLA 是可选 baseline。
- 项目使用 LeRobot `0.6.2`，commit 为 `22bd7a2f489b367d8df42de803b1e8c4ca63a3f9`。
- 本地 Windows 仅用于 Codex、Git、源码阅读、脚本、笔记和结果索引；VLA runtime 只在远程执行。
- 主要远程 GPU 为 NVIDIA RTX 6000D，`nvidia-smi` 报告 85,651 MiB VRAM。
- 主要持久化数据根目录为 `/root/autodl-tmp`，容量 150 GB。
- 已验证 runtime：Python 3.12.13、PyTorch 2.8.0+cu128、torchvision 0.23.0+cu128、TorchCodec 0.7.0、FFmpeg 7.1.1、hf-libero 0.1.4。
- LIBERO `libero_10` task 0 可以初始化、reset、返回 `pixels` 和 `robot_state`、暴露 7 维 action 并正常关闭。
- 2026-08-11 完成 20-step Pi0.5 LIBERO sanity training：batch size 1、BF16、gradient checkpointing、expert-only、冻结 vision encoder。
- Sanity run 峰值 allocated/reserved 显存为 12.8482/13.0039 GiB，loss 有限、无 OOM，并保存 step-20 checkpoint。
- Sanity run 平均 step 为 0.4728 秒（包含首批加载），steps 2–20 平均为 0.2454 秒。这不是 Rollout latency 或正式训练吞吐结论。
- 正式 2,000-step Pi0.5 expert-only 第一阶段完成，配置为 batch size 1、BF16、gradient checkpointing，并保存 1k/2k checkpoint。峰值显存 12.8482/13.0039 GiB，无 OOM。
- 在固定匹配协议（`libero_10` task 0、seeds 1000–1009）中，pretrained 为 0/10，2k 为 10/10。这是单个重点任务的结果，不是完整 LIBERO 分数。
- Pretrained 与 2k 平均模型推理延迟分别为 181.61 ms 和 168.99 ms；两者都使用 BF16 和 `n_action_steps=10`。
- 项目已在计划的 2k 决策点停止，没有执行 5k/10k 或完整 LIBERO evaluation。
- 旧 RTX 4090 数据已在迁移后通过 hash 验证，该服务器可以保持关机。
- Checkpoint 001000 在固定初态 0–9 上为 9/10，唯一失败为 state 4 达到 520-step horizon。
- Checkpoint 002000 在连续一次运行中覆盖唯一固定初态 0–29，结果 28/30；失败为 state 14 和 18，无 OOM。
- 2k 统一运行的前十个 episode 完全复现早期十集的 success flag 和 episode length。匹配前十个状态上，1k 为 9/10，2k 为 10/10。
- 在此协议中，episode seed label 不负责选择 fixed init state。每个新评测进程中，LeRobot 从 `.pruned_init` index 0 开始依次推进；重启进程会重新从该 index 开始。
- 该任务有 50 个按完整行 hash 验证唯一的存储 init-state row。固定同一 row 但改变 seed 时，测得首个 observation 相同；连续存储 row 会改变 pixels 和 robot state。
- 扩展后的 2k 结果支持同任务 fixed-initial-state 稳定性，不支持 unseen-seed、unseen-layout、完整 LIBERO 或泛化结论。
- 视频审查发现 1k 有一次 grasp-acquisition/retry failure；2k 状态 14、18 出现明显 wrong-object-selection failure。因未记录内部 policy signal、contact 或 object-ID log，根因解释仍是假设。
- 前 30 个固定状态后选择决策 B：保留 checkpoint 002000，并在增加训练步数前做有意义的额外条件检查。随后已评测固定状态 30–49，没有继续训练。
- Training exposure audit 纠正了实验描述：实际 2k run 使用完整 `lerobot/libero` 的 40 个任务，没有 task filter，不是针对 `libero_10` task 0 的 task-specific fine-tuning。
- 固定训练数据包含 1,693 episodes、273,465 frames 和 40 tasks。重点 task-0 指令在数据集中是 `task_index=5`。
- 起始 checkpoint 为 `lerobot/pi05_libero_base`；当前 LeRobot docs 将其描述为专门在 LIBERO 上训练，精确样本级 exposure 未由所检查文件公开。
- 40 任务数据集中没有任务对本次 2k fine-tuning 属于 unseen。原计划的 60-episode cross-task transfer comparison 因此被跳过，不存在 retention/transfer 结论。
- 此前未评测的固定初态 ID 30–49 在 checkpoint 002000 下为 18/20，mean/median length 304.35/282.0，无 OOM。
- 全部固定状态 0–49 上 checkpoint 002000 为 46/50（92.0%）。这是同任务 fixed-initial-state robustness，不证明这些状态未参与模型训练。
- 50 个状态中的四个 2k 失败均明显涉及错误物体选择；不能证明内部 language/VLM root cause。
- Phase 1 实验已完成。下一步是整理 README 和面试材料；LIBERO-plus 保持可选且未安装。

## 2026-08-12：Phase 2 / Step 3 已验证事实

- 真实链路：Isaac/ROS 2 静止 Observation → 项目 Policy Input Adapter → LeRobot 真实 LIBERO/Pi0.5 processor → Phase 1 2k checkpoint → Action Chunk。
- 输入：两路 256×256 RGB、8D `[EEF xyz, EEF axis-angle, two finger qpos]`、语言 `move the robot arm`。
- 8D state 的结构和计算链通过；跨 Isaac/LIBERO 的坐标域、gripper convention、相机标定和移动场景同步尚未完成，兼容性为 PARTIAL。
- `predict_action_chunk` 真实调用 3 次；每次 `[1,50,7]`、float32、全部 finite；延迟 407.157/186.766/186.218 ms，mean 260.047 ms，p95 385.118 ms。
- Torch peak allocated/reserved 为 8.870/9.201 GiB；无 OOM；模型载入 99.004 秒。
- Pi0.5 7D 是相对 EEF OSC_POSE + gripper；Isaac `/joint_command` 是 7 关节绝对位置，直接映射为 MISMATCH。
- 没有发布或执行 VLA action；没有 Rollout、Evaluation 或 Step 4；完成后 GPU 0 MiB。

## 2026-08-12：Phase 2 / Step 4 已验证事实

- 实际安装的 robosuite 1.4.0 确认 7D action 是 3D 无量纲平移输入、3D 无量纲轴角输入和 1D gripper；环境分别缩放到每轴 ±0.05 m 与 ±0.5 rad。
- 姿态组合为 `R_target = R_delta @ R_current`，即 spatial/world-frame 左乘；不能直接相加 axis-angle。
- Isaac 6.0.1 使用非 deprecated 的 `PinkIKController + load_pink_supported_robot("franka") + OSQP`。
- 三轴 5 mm 合成平移、三轴 0.02 rad 合成旋转和 OPEN/CLOSE/NEUTRAL 夹爪测试全部通过。
- 2k checkpoint 只调用一次 `predict_action_chunk`，只执行 `action_chunk[0]`；剩余49步未执行，没有第二次 inference 或 closed loop。
- VLA 动作执行后 Franka 实际移动；目标位置误差 1.115 mm、姿态误差 7.030 mrad；inference 577.160 ms、adapter 0.407 ms、PINK mean 1.950 ms；无 OOM。
- 真实前后 PNG 与 9 秒 MP4 已保存。当前停在 Step 4，未抓取、未评测任务成功率、未进入 Step 5。

## 2026-08-12：Phase 2 / Step 5 已验证事实

- 同一 Isaac 场景完成严格 5 轮 closed-loop runtime；每轮重新采集两路 RGB 与 8D robot state，真实调用一次 Pi0.5，并只执行 50×7 chunk 的索引 0。
- 五组 external/wrist 图像均唯一，所有相邻 robot state 与首动作均发生变化；真实 inference 总数为 5，剩余49步执行数始终为 0。
- 推理 mean/median/p95 为 233.742/187.041/374.803 ms；Cycle 1–4 steady-state mean 为 186.743 ms。Action Adapter mean 0.265 ms，PINK mean 1.876 ms。
- 起终点 EEF 直线位移 25.384 mm，累计关节端点位移 0.288697 rad；五轮 Safety 均 PASS，无拒绝、超时、workspace violation 或 joint violation。
- Torch peak allocated/reserved 为 8.868/9.199 GiB；无 OOM。最终无实验进程和 GPU compute process，LeRobot upstream clean。
- Step 5 只证明 closed-loop runtime。没有评测任务成功、抓取、LIBERO transfer、zero-shot manipulation 或 cross-domain generalization；当前停在 Step 5。

## 2026-08-12：Phase 3 / Step 6 冻结事实

- 当前最新阶段为 Step 6 完成，前文“停在 Step 5”已过时。
- 任务：`libero_10` task 0；Phase 1 数据集 `task_index=5`；指令为 `put both the alphabet soup and the tomato sauce in the basket`。
- Step 6 是同语义任务的 LIBERO → Isaac cross-simulator/cross-environment evaluation，不是 unseen-task、zero-shot new-task、open-world 或 sim-to-real。
- checkpoint：`results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model`；没有训练、LoRA、Full Fine-Tuning 或权重更新。
- 三个正式 episode 只使用 fixed initial state 0、1、2；每次独立 Isaac 进程 hard reset；每回合最多 100 cycles；K=1，只执行 50×7 chunk 的 index 0。
- Success 复现当前 LIBERO 有效谓词：alphabet soup 与 tomato sauce 的 body center 同时位于 basket contain site 定向 box；positive/negative tests 均 PASS。
- Episode 0/1/2 均为 100 cycles、HORIZON_REACHED、FAIL；wall time 202.552/193.751/197.332 秒。总 success=0/3。
- 三回合无 OOM、无人工干预、无 safety/IK/workspace 异常。Experimental Pipeline=PASS，Task Transfer=FAIL。
- 300 次推理 mean/median/p95=182.876/181.603/184.141 ms；steady-state mean=181.916 ms；Torch peak allocated/reserved≈8.87/9.20 GiB；nvidia-smi peak=13,059 MiB。
- Observed behavior：机械臂运动到任务区/篮子附近，但两个目标物体在三个 episode 中的测得位移均为 0；失败分类为 failed approach、failed grasp、horizon reached。
- 视觉域、相机、状态分布、action/control、gripper/physics 差异均只是可能解释，未证明任何 Pi0.5/VLM 内部根因。
- 三段 MP4、300 轮结构化证据、对照图、场景/成功判定审计与文件哈希均已保存。完成后 GPU 0 MiB/0%，停在 Step 6，Ready for Step 7=NO。
