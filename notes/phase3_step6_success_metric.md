# Phase 3 / Step 6：成功判定

## 判定公式

对 alphabet soup 和 tomato sauce 的刚体中心分别执行：

1. 将 world center 转到 `basket_1_contain_region` 的局部定向坐标系；
2. 检查三个轴是否都满足 `abs(local_xyz) <= [0.06108, 0.06108, 0.06949]`；
3. 两个物体同时 inside 才返回 task success。

这复现了当前安装 LIBERO 的有效 `In` 谓词，不把“夹爪闭合”“碰到物体”或“机械臂进入篮子”当作成功，也没有另加会改变原始语义的稳定性条件。

## 合成测试

- Positive：两个测试 center 均放在 contain box 内 → `success=true`。
- Negative：一个测试 center 放在 x half extent 外 1 cm → `success=false`。
- 结果：两项均 PASS，证据见 `results/phase3_step6/success_detector_test.json`。

正式三个 initial state 在 rollout 前均为 `success=false`，不存在从已完成状态起跑的问题。
