# Phase 2 / Step 3 Pi0.5 兼容性报告

| 项目 | 判定 | 证据与边界 |
| --- | --- | --- |
| Images | PARTIAL | 两路均为真实 256×256 RGB、HWC uint8；进入 LeRobot 后为 BCHW float32 `[0,1]`，LIBERO processor 做 180° 翻转，Pi0.5 内部 resize/pad 至 224 并映射到 `[-1,1]`。第二路只是手腕跟随视角，不是已标定 eye-in-hand。 |
| Robot State | PARTIAL | 真实构造 `[EEF xyz, axis-angle, 2 finger qpos]` 共 8 维，表示和算法匹配；Isaac 与 LIBERO 的参考域和 gripper 量程未标定，EEF 文件与 ROS 消息也没有移动场景所需的同步机制。 |
| Language | MATCH | 固定字符串 `move the robot arm` 通过 checkpoint 的真实 Pi0.5 state-prompt/tokenizer processor，得到 `[1,200]` token 与 attention mask。语句只用于接口测试，不代表已定义 Isaac 任务。 |
| Policy Input | PARTIAL | 必需 key、shape、dtype、device 均通过真实 processor；但传感器/坐标域语义仍存在上述未对齐项。 |
| Pi0.5 Runtime | PASS | 2k checkpoint 全权重加载成功，3 次真实 `predict_action_chunk` 均完成，无 OOM。 |
| Action output | PASS | 每次 `[1,50,7]`、float32、全部 finite；经过真实 checkpoint postprocessor。 |
| Action → Isaac Controller | MISMATCH | Pi0.5 是相对 EEF OSC_POSE + gripper；Isaac 当前接口是 7 关节绝对位置。 |

成功输出 Action Chunk 只证明 Observation 可以进入 Pi0.5 且 runtime 可以产生数值，不证明 Action 已经可以控制 Isaac Franka。
