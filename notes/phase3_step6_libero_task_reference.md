# Phase 3 / Step 6：LIBERO 原始任务审计

## 任务身份

- Task suite：`libero_10`
- Suite task ID：`0`
- Phase 1 数据集中的 `task_index`：`5`（这是数据集索引，不等同于 suite task ID）
- 指令：`put both the alphabet soup and the tomato sauce in the basket`
- BDDL：`LIVING_ROOM_SCENE2_put_both_the_alphabet_soup_and_the_tomato_sauce_in_the_basket.bddl`
- BDDL SHA-256：`2e661058917f683a25bce480015197f0a2c1911bcbc2b9dd9d947199069c9618`
- Robot：robosuite `SingleArm` + LIBERO `OnTheGroundPanda`
- 控制频率：20 Hz；MuJoCo timestep：0.002 秒；Phase 1 horizon：520 control steps

本记录来自 RTX 6000D 服务器上实际安装的 `hf-libero 0.1.4`、`robosuite 1.4.0` 源码和真实 task-0 runtime，不是凭记忆重建。

## BDDL 对象与目标

任务包含 alphabet soup、tomato sauce、basket，以及 cream cheese、ketchup、orange juice、milk、butter 等干扰物。目标谓词为：

```text
And(
  In(alphabet_soup_1, basket_1_contain_region),
  In(tomato_sauce_1, basket_1_contain_region)
)
```

初始放置范围：basket 的 x/y 分别为 `[-0.01, 0.01]` / `[0.25, 0.27]`；tomato sauce 为 `[-0.125, -0.075]` / `[0.025, 0.075]`；alphabet soup 为 `[-0.125, -0.075]` / `[-0.175, -0.125]`；三者 yaw 均固定为 0。Step 6 没有重新随机采样，而是读取固定 initial state 0、1、2 的实际稳定后位姿。

## 几何、相机与机器人

- 逻辑 tabletop full size：`0.70 × 1.60 × 0.024 m`，offset `(0, 0, 0.41)`。
- 运行时实际 task-relevant tabletop 碰撞 box：中心 `[-0.25, 0.05239, 0.42492] m`，half extents `[0.01184, 0.44432, 0.67171] m`。
- robot base：`[-0.51, 0, 0.42] m`，单位四元数。
- external camera：位置 `[0.60657737, 0, 0.96] m`，vertical FOV 45°。
- wrist camera：父节点 `robot0_right_hand`，局部位置 `[0.05, 0, 0] m`，vertical FOV 75°。
- Phase 1 评测图像为 360×360；Pi0.5 policy 输入为两路 256×256。

三组固定初态的完整 joints、EEF、目标物体与篮子位姿保存在 `results/phase3_step6/initial_states/`，原始 LIBERO 截图和 runtime 元数据保存在 `results/phase3_step6/libero_reference*/`。

## LIBERO success 的真实语义

安装源码中 `In.__call__` 调用 `container.check_contact(object) and container.check_contain(object)`。这里 container 是 `basket_1_contain_region` 对应的 `SiteObjectState`；其 `check_contact` 恒为真，因为 site 没有动态接触实体，实际有效条件是目标物体 body center 位于 basket contain site 的定向 box 内。

contain site 的局部中心为 `[0, 0, 0.07185] m`，half extents 为 `[0.06108, 0.06108, 0.06949] m`。因此 Step 6 的 Isaac detector 复现“两个目标 body center 都位于该定向 box 内”，没有另加会改变 LIBERO 成功语义的稳定性或接触条件。
