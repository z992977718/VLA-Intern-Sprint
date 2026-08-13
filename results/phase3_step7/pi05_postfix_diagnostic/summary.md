# Phase 3 / Step 7D：一次性修复后 Pi0.5 诊断

- 类型：**DIAGNOSTIC / NOT COUNTED**
- Episode：1（Step 6 fixed initial state 0）
- Horizon：最多 100 cycles
- K：1，只执行 `action_chunk[0]`
- 结果：**DIAGNOSTIC TASK FAILURE**
- 行为变化：**NO_CLEAR_IMPROVEMENT**
- 建议：**FREEZE_FRANKA_ISAAC_MAINLINE**

## Before / After

| 指标 | Step 6 BEFORE | Step 7D AFTER | 数值变化 |
|---|---:|---:|---:|
| episode result | horizon_reached | HORIZON_REACHED | None |
| cycles | 100 | 100 | 0.0 |
| EEF endpoint path length (m) | 0.9443713671454167 | 0.7797247523926571 | -0.16464661475275955 |
| min distance to alphabet (m) | 0.2581492384773509 | 0.2630737577490472 | 0.004924519271696293 |
| min distance to tomato (m) | 0.19347688131117 | 0.20132251647793192 | 0.007845635166761927 |
| alphabet max displacement (m) | 0.0 | 0.0 | 0.0 |
| tomato max displacement (m) | 0.0 | 0.0 | 0.0 |
| close attempts | 83 | 64 | -19.0 |
| Safety violations | 0 | 0 | 0.0 |
| IK failures | 0 | 0 | 0.0 |
| mean inference latency (ms) | 185.20261247642338 | 259.7686639428139 | 74.56605146639049 |
| median inference latency (ms) | 181.4287258312106 | 237.0580779388547 | 55.62935210764408 |
| p95 inference latency (ms) | 184.70116059761494 | 322.76013838127255 | 138.0589777836576 |

## 证据边界

本次同时继承 State Mapping、浮点安全检查和 7D PINK 三组已确认修复，不能把行为变化归因于其中某一个单独修复。无论诊断成功或失败，本回合都不构成新 benchmark 成功率；也不能据此把原 Step 6 的 0/3 单独归因于已修复的机器人侧问题。

仍保留：orientation mapping 未解决、约 0.15 s image-state skew 未修复、跨模拟器视觉/域差异，以及控制器/embodiment 差异。
