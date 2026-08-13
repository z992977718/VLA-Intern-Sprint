# Phase 3 / Step 7B: State Frame Tree

## LIBERO

```text
MuJoCo world
  -> robot base / robot model
     -> robot0_eef observable
        position: robot0_eef_pos
        orientation: robot0_eef_quat (xyzw)
        used by Pi0.5 state: yes
     -> controller EEF
        orientation: controller.ee_ori_mat
        used by Pi0.5 state: no; diagnostic only
```

## Isaac

```text
/World
  -> /World/panda
     -> /World/panda/panda_hand
        position: USD world pose
        orientation: USD quaternion (wxyz)
     -> current tool point
        local translation: [0, 0, 0.0951034858] m
        world position: hand_position + R_hand @ offset_local
        orientation: currently panda_hand orientation
```

当前 adapter 使用 tool point 的位置与 `panda_hand` 姿态。它们并非已由五姿态证明与 LIBERO `robot0_eef` 是同一刚体参考点。`controller.ee_ori_mat` 相对 `robot0_eef_quat` 存在恒定约 1.571 rad 的控制器约定差异，但该矩阵不是 policy state 输入，不能把它当作 Pi0.5 姿态错误的证据。
