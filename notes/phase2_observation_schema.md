# Phase 2 / Step 2：Phase 1 Observation 真实 Schema 审计

## 审计范围

本文件只描述当前固定 LeRobot commit `22bd7a2f489b367d8df42de803b1e8c4ca63a3f9`、`lerobot/libero` revision `a1aaacb7f6cd6ee5fb43120f673cebb0cfea7dd4` 和 `lerobot/pi05_libero_base` 所形成的 Phase 1 接口。证据来自数据集 `meta/info.json`、LeRobot 源码、实际训练/评测配置，不用常识补字段。

## 1. 图像

| 项目 | 已核实结果 |
| --- | --- |
| 实际图像路数 | 2 路真实 RGB；policy 配置另有 `empty_cameras=1`，这是缺失相机 padding，不是第三路真实传感器 |
| 数据集 feature key 1 | `observation.images.image`，来源 `pixels/agentview_image`，场景/第三人称视角 |
| 数据集 feature key 2 | `observation.images.image2`，来源 `pixels/robot0_eye_in_hand_image`，腕部视角 |
| 数据集原始尺寸 | 两路均为 HWC `256×256×3`、`uint8`、10 FPS |
| Phase 1 Rollout 原始尺寸 | 环境按 `360×360×3` 产生两路 RGB |
| 进入 policy 前 | `ObservationProcessorStep` 将 HWC uint8 转成 BCHW float32，并除以 255 得到 `[0,1]` |
| policy 内部 | Pi0.5 `_preprocess_images` 对非 `224×224` 输入执行 `resize_with_pad_torch(..., 224, 224)`，再从 `[0,1]` 映射到 `[-1,1]` |

因此，不能只说“原图是 256”或“评测图是 360”：训练数据源为 256，Phase 1 闭环评测环境源为 360，模型实际视觉输入最终为带 padding 的 224。

## 2. Robot state

Policy feature key 是 `observation.state`，实际维度为 8，顺序由 `LiberoObservationProcessorStep` 源码确定：

| 索引 | 语义 |
| ---: | --- |
| 0 | 末端执行器位置 x |
| 1 | 末端执行器位置 y |
| 2 | 末端执行器位置 z |
| 3 | 末端执行器姿态 axis-angle x |
| 4 | 末端执行器姿态 axis-angle y |
| 5 | 末端执行器姿态 axis-angle z |
| 6 | gripper qpos 第 1 维 |
| 7 | gripper qpos 第 2 维 |

原始 LIBERO observation 中还有末端 quaternion/rotation matrix、关节位置/速度和 gripper velocity，但当前处理器没有把它们全部拼进 Pi0.5 的 8 维输入。

## 3. Language/task

- 环境把 LIBERO task 的 `task.language` 保存为 `task_description`。
- Rollout 管线把任务文本放入 complementary data 的 `task` 字段。
- Pi0.5 processor 先取得归一化后的 state，把语言和离散化 state 组合为 `Task: <language>, State: <bins>;\nAction: `，再交给 `google/paligemma-3b-pt-224` tokenizer。
- 因此语言不是 Observation 数值向量的一部分，但它是 policy processor 的必需输入。

## 4. Action

数据集 feature key 是 `action`，实际维度 7，范围 `[-1,1]`。当前环境使用 robosuite `OSC_POSE` 且 `control_mode=relative`：

| 索引 | 源码可支持的语义 |
| ---: | --- |
| 0–2 | 末端位置的相对/增量命令 x、y、z |
| 3–5 | 末端姿态的相对旋转命令，scaled axis-angle 三维 |
| 6 | gripper 标量命令；当前 robosuite 1.4.0 `PandaGripper.format_action` 明确规定 `-1 = open`、`+1 = closed` |

注意：数据集 `meta/info.json` 的 `names` 只有笼统的 `actions`，没有逐维名字。逐维语义由当前运行环境中的 LIBERO `OSC_POSE` 与 robosuite 1.4.0 Panda gripper 源码交叉确认，而不是从数据元数据猜测。

## 结论

Phase 1 Pi0.5 实际期望的是“两路具有特定视角语义的 RGB + 末端笛卡尔位姿/夹爪组成的 8 维 state + task language”，并输出 LIBERO OSC_POSE 语义的 7 维相对 action。它不是“任意两张图片 + 任意 8 个机器人数值 + 任意 7 维控制量”。
