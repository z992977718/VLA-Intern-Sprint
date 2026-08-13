# Phase 3 / Step 7B.1：位置映射修复

## 修复前

旧逻辑从 `panda_hand` world pose 计算：

```text
p_tool = p_hand + R_hand @ [0, 0, 0.0951034858]
```

该 95.1035 mm 向量会随手腕朝向旋转，所以 Step 7B 没有发现 world-fixed offset bug。但它不是当前 USD 资产最合适的原生工具点。

## 修复后

使用实际 USD 子 prim：`/World/Robot/panda_hand/tool_center`。

```text
T_world_equiv_eef = T_world_hand @ T_hand_tool_center
```

运行时直接读取 `tool_center` 的 world pose；`T_hand_tool_center` 来自 USD 的真实父子刚性关系，未依据五姿态拟合任何世界坐标常数。

## 判定

calibration 与独立 hold-out 都保持约 8 mm 的位置残差，故为 `APPROXIMATE`。这说明位置语义显著更合理，但不能写成精确 match。
