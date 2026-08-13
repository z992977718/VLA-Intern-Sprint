# Phase 3 / Step 7C.1：Tomato Descent Safety-Stop 静态定位

## 结论

三次 tomato 正式 trial 可以一致定位到：**approach 已完成，descent 的第 0 个控制迭代被安全层拒绝**。

现有证据仍不能区分以下底层条件：

- PINK 输出包含非有限值；
- 最大关节目标跳变超过 `0.05 rad`；
- 某关节目标低于运行时下限；
- 某关节目标高于运行时上限。

因此准确根因状态为 `UNRESOLVED_FROM_EXISTING_LOGS`，不是已修复。

## 为什么能定位到 descent step 0

每个 tomato 目录都保存了 23 张帧：1 张 start、1 张 open、21 张 approach，没有 descent 帧。代码在 descent 第 0 步安全检查通过并执行一个 physics step 后必定立即保存一张 descent 帧。异常堆栈又明确来自 `execute_stage("descent", ...)` 的安全分支，因此拒绝发生在 descent step 0。

三次 `exception.txt` 内容和 SHA-256 完全相同，但这只能证明相同的高层异常位置，不能证明四个底层布尔条件中的同一个条件为真。

## 已排除或不能作为直接触发条件的项目

- Step 7C Oracle 没有 Cartesian workspace min/max 分支，不能套用 Step 6 的 workspace 常量解释本次异常。
- PINK `reset` 没有失败，`forward` 也没有返回 `None`；否则会进入明确的 `IK_FAILURE` 分支。PINK 已返回目标，但目标可能非有限或被安全层判定不可接受。
- tomato 尚未进入 close/lift，因此不能把失败归因于接触、夹爪力、摩擦、质量、碰撞或抓取后掉落。
- 本实验未使用 Pi0.5、相机或 observation，不能归因于 Pi0.5、视觉模块或 `0.15 s` timestamp skew。

## 几何与成功 alphabet 对照

成功的 `alphabet_00` 保存了完整目标：pre-grasp z=`0.609104 m`、grasp z=`0.524104 m`、lift z=`0.669104 m`，approach/descent 末端误差分别为 `2.430 mm` 和 `1.614 mm`。

现有 Step 6 dynamic scene export 中 tomato 的根位置与近似碰撞盒均为有限值。按标量 z 参数重建的 grasp/pre-grasp/lift 约为 `0.523242/0.608242/0.668242 m`，与 alphabet 的高度尺度接近；三张最终 approach 帧也显示夹爪已位于 tomato 上方。由于失败 trial 没有保存 live Gf 几何和精确 target，这些信息只能说明“未发现明显无效几何”，不能证明几何完全正确。

## 下一步（只提出，不执行）

最小修改应当只是增加安全遥测：在抛出异常前分别保存 finite、delta、lower-limit、upper-limit 四个布尔结果，以及 joint target/actual、逐关节 delta、argmax、limits/margins 和 EEF target/actual。不得改变 `0.05 rad` 阈值或任何物理参数。

若之后获得用户明确授权，只需要运行 **一次 `DIAGNOSTIC / NOT COUNTED` tomato trial** 来获得精确触发条件。当前不应执行 Pi0.5 diagnostic rollout。
