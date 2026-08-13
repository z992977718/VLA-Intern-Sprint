# Phase 2 / Step 5：Closed-loop VLA Runtime Smoke Test

结论：**PASS**。在同一 Isaac Sim 场景中完成 5 轮 receding-horizon 闭环。每轮重新采集两路 RGB 与 8D state，真实调用一次 Pi0.5 `predict_action_chunk`，只执行 `action_chunk[0]`，再采集下一轮 Observation。

- 推理延迟：mean 233.742 ms，median 187.041 ms，p95 374.803 ms；去掉 Cycle 0 warm-up 后 mean 186.743 ms。
- EEF 起点/终点：`[0.38924744725227356, 0.004671569913625717, 0.4562399685382843]` → `[0.38925689458847046, 0.023057324811816216, 0.4387386441230774]`；直线位移 25.384 mm。
- Torch peak allocated/reserved：8.868/9.199 GiB；OOM=false。
- 成功运行的安全拒绝、超时、workspace violation、joint violation 均为 0。
- Attempt 001 因 PINK `position_cost` 传入整数而在 Cycle 0 前失败，执行动作数为 0；修正为浮点数后重新运行。

本结果只证明 runtime 闭环工作；没有布置任务物体，没有评测抓取或 task success，也不声称 LIBERO transfer、zero-shot manipulation 或跨域泛化。
