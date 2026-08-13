# Phase 3 / Step 6：跨仿真失败与 Domain Gap 分析

## 已知 Domain Differences

- Simulator/physics：LIBERO 使用 MuJoCo/robosuite，Isaac 使用 PhysX。
- Renderer/lighting/background：渲染器、光照、阴影、墙面和干扰物不同。
- Target collision：目标罐视觉网格相同，但 Isaac 碰撞简化为 mesh bounds 单 box。
- Camera：external 参数对齐但渲染实现不同；wrist 是经初态标定的 rigid-follow 映射。
- State/control frame：使用 95.1035 mm 固定工具点偏移对齐 EEF，属于校准近似。
- Gripper/controller：夹爪关节、接触动力学和 PINK 闭环与 robosuite OSC_POSE 不同。

## Observed Behaviors（真实观察）

- 三个 episode 都完成 100 cycles，均为 `HORIZON_REACHED`，无安全停止、IK failure、workspace stop 或 OOM。
- 机械臂有明显连续运动，EEF path 分别为 0.9444、1.1499、0.7434 m。
- 从代表帧和完整 MP4 可见，机械臂会向桌面任务区域和篮子附近移动。
- 三个 episode 的 alphabet soup 和 tomato sauce 测得位移均为 0 m，没有形成有效接近后的接触、抓取、搬运或放置。
- 因而失败分类为：`failed approach`、`failed grasp`、`horizon reached`。没有证据支持 wrong-object interaction、object dropped 或 failed transport。

## Possible Explanations（假设，不是已证明内部原因）

- 视觉域差异或相机差异可能使 policy 输入偏离训练分布；
- EEF/state calibration 与训练时状态分布仍可能不完全一致；
- Action Adapter 的保守裁剪、PINK dynamics 或夹爪接触差异可能影响靠近与抓取；
- 去除干扰物和更换背景也可能改变 policy 的视觉上下文。

不能据此断言“VLM 视觉模块失败”“语言理解失败”或某个内部网络部件是根因。当前结论只到行为层：跨仿真闭环能运行，但同语义任务在本协议下 0/3。
