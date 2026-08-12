# 下一阶段决策

## 决策：B

保留 checkpoint 002000，在增加训练步数前优先设计真正面向泛化的测试。

直接证据：

- pretrained：0/10；
- 1k：固定状态 0–9 上 9/10；
- 2k：相同固定状态上 10/10，固定状态 0–29 上 28/30；
- 2k 匹配子集在两次独立运行中完全复现；
- 无 OOM 或 runtime instability；
- 1k 到 2k 的 checkpoint loss 并非单调下降，不能假定更多 optimizer step 会等比例提升闭环表现；
- 剩余 2k 失败是有结构的错误物体选择行为，而非基础设施故障。

这使 B 比 A 更有信息价值：checkpoint 在已测的单任务固定状态分布上已经较稳定，再加入一段未经检查的训练，其诊断价值低于测试 learned behavior 是否能迁移。未选择 C，因为协议精确复现，且没有异常指标、OOM 或评测不稳定。

## 决策边界

这里的“较稳定”只表示一个任务、30 个唯一存储初态上的 28/30，并不表示已经解决。仍有两次失败，95% Wilson interval 为 78.7%–98.2%，也未测试 unseen task 或独立随机布局。

如后续指令授权新实验，应优先定义会改变有意义因素的 generalization protocol，例如新增存储初态 30–49 或另一个 LIBERO task，同时固定 policy 和 evaluation settings。只改变 seed label、但每次重新从同一个 `.pruned_init` row 开始，不是有效泛化测试。

## 停止条件

作出该决策后，没有启动 5k/10k training、新 Rollout batch、更广 evaluation、GPU/model 切换或上游源码修改。
