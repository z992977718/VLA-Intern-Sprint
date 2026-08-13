# Phase 2 / Step 4 学习笔记

以下每项包含专业解释、小白理解和本项目作用。

## 1. Task Space
专业：用末端执行器的位置和姿态描述控制目标。小白：告诉机械手“手要到哪里”。本项目：Pi0.5 的前六维对应末端增量。

## 2. Joint Space
专业：用各关节角描述机器人构型。小白：告诉每个关节转多少。本项目：PINK 最终输出 Franka 关节目标。

## 3. 为什么 7 维不是 7 个关节
专业：LIBERO 的 7 维是 6D 末端增量加 1D 夹爪。小白：六维管手的位置姿态，一维管开合。本项目：不能直接发布到七轴 `/joint_command`。

## 4. Delta Position
专业：相对当前末端位置的 Cartesian 位移。小白：从现在的位置再挪一点。本项目：环境输入乘 0.05 m 后加到当前位置。

## 5. Delta Orientation
专业：相对当前姿态的增量旋转。本项目使用 world/spatial 左乘。小白：在当前朝向基础上再转一点。本项目：环境输入乘 0.5 rad 后组合旋转矩阵。

## 6. 为什么轴角不能简单相加
专业：三维旋转不满足普通向量加法，组合顺序会改变结果。小白：先绕 x 再绕 y 和反过来不一样。本项目：使用 `R_delta @ R_current`。

## 7. Coordinate Frame
专业：定义位置和方向参考基准。小白：同一句“向右”必须先说明站在谁的视角。本项目：验证 LIBERO spatial delta 到 Isaac `/World` 的轴映射。

## 8. World Frame 与 EEF Frame
专业：World 固定在场景，EEF 随末端移动。小白：一个是房间坐标，一个是手掌坐标。本项目：robosuite 左乘增量对应 world/spatial frame。

## 9. Action Scaling
专业：把无量纲 controller input 映射为物理位移或角度。小白：模型输出的 0.1 不等于 0.1 米。本项目：0.1 平移输入对应 5 mm。

## 10. Action Adapter
专业：将策略动作语义转换为目标机器人控制接口。小白：是 AI 和机器人之间的翻译器。本项目：完成缩放、坐标转换、姿态组合和夹爪映射。

## 11. IK
专业：由末端目标反求关节构型。小白：知道手要到哪，算出各关节怎么配合。本项目：由 PINK 完成。

## 12. PINK / task-space controller
专业：PINK 以加权任务和约束求解 differential IK，并积分得到关节目标。小白：每个仿真步都算一小步让手靠近目标。本项目：使用 Isaac 6.0.1 官方实现。

## 13. Joint Target
专业：关节位置控制器追踪的目标角度。本项目中双指目标单位是米。小白：下层控制器真正接收的数字。本项目：发送前检查 finite、限位和最大步长。

## 14. Safety Layer
专业：在模型与执行器之间强制实施确定性约束和拒绝策略。小白：AI 即使说错了，安全门也能拦住。本项目：限制位移、旋转、workspace 和关节目标。

## 15. 为什么只执行一个 VLA Action
专业：先隔离验证动作语义和适配器，避免长 chunk 放大误差。小白：先迈一步确认方向，不连续走 50 步。本项目：只执行 index 0，剩余49步为0次执行。

## 16. Step 4 与 Step 5
专业：Step 4 是单次 open-loop action execution；Step 5 才可能涉及新 Observation、再次 inference 和 closed-loop。小白：Step 4 只试一步，Step 5 才可能边看边走。本项目当前停在 Step 4。
