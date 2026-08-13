# Phase 3 / Step 6：LIBERO → Isaac 场景映射

| 项目 | LIBERO | Isaac Sim | 状态 |
| --- | --- | --- | --- |
| Robot | OnTheGroundPanda | Isaac 官方 Franka Panda | APPROXIMATE：同类机器人，资产和动力学不同 |
| Robot base | `[-0.51,0,0.42]` | 同一 world pose | MATCH |
| 初始 arm joints | 固定 state 0/1/2 实测值 | 每个 episode 独立设置后 hard reset | MATCH |
| EEF/control point | `robot0_eef` | `panda_hand` + 局部 z 方向 95.1035 mm 偏移 | CALIBRATED APPROXIMATE |
| 桌子视觉 | LIBERO living-room table OBJ，scale 1.5 | 同一 OBJ 转 USD，scale 1.5 | MATCH；缺失一个源目录原本不存在的 bump map |
| 桌面碰撞 | runtime MuJoCo tabletop box | 同一中心、姿态、half extents | MATCH_FOR_TASK_TOP |
| Soup/Tomato 视觉 | LIBERO OBJ/texture，scale 0.01 | 同一 OBJ/texture 转 USD，scale 0.01 | MATCH |
| Soup/Tomato 碰撞 | 多 box MuJoCo collision set | 按真实 mesh bounds 的单 box | APPROXIMATE ASSET |
| Basket | LIBERO OBJ + 5 box colliders | 同一 OBJ + XML 中 5 个 box | MATCH |
| 初始物体 pose | 固定 initial state 0/1/2 稳定后位姿 | 逐 episode 写入相同位姿 | MATCH |
| External camera | 实测 world pose，FOV 45° | 同一 pose/FOV，256×256 | MATCH_PARAMETERS；renderer 不同 |
| Wrist camera | robot0_right_hand 局部相机 | 初始 world pose 对齐后刚性跟随 panda_hand | APPROXIMATE |
| Lighting/background | LIBERO living room、墙面、干扰物 | 中性灯光/背景，无四个干扰物 | APPROXIMATE |
| Physics | MuJoCo | PhysX | APPROXIMATE / UNKNOWN 等价性 |
| Gripper | robosuite Panda gripper | Isaac Panda parallel fingers | APPROXIMATE：范围、符号和接触动力学不同 |
| Action | LIBERO relative OSC_POSE | 同语义 Action Adapter → Safety → PINK | CALIBRATED APPROXIMATE |

真实视觉网格来源、SHA-256、USD 路径和转换后哈希见 `results/phase3_step6/asset_conversion.json`。本项目没有修改 LIBERO 或 LeRobot 上游源码，也没有重复下载已有资产。
