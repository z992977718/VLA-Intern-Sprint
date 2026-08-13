# Phase 3 / Step 7B.1：夹爪状态映射修复

## 真实数据证据

LIBERO 静态读取：

| 状态 | LIBERO qpos | Isaac qpos |
|---|---|---|
| open | `[0.04, -0.04]` | `[0.04, 0.04]` |
| intermediate | `[0.02, -0.02]` | `[0.02, 0.02]` |
| closed | `[0, 0]` | `[0, 0]` |

固定 revision `a1aaacb7f6cd6ee5fb43120f673cebb0cfea7dd4` 的全量 273,465 帧统计也显示两维几乎总是相反符号，`opposite_sign_fraction = 0.99876767`。

## 映射

```text
Isaac physical [finger1, finger2]
=> LIBERO-compatible [finger1, -finger2]
```

open、intermediate、closed 的 CPU 单元测试已在远程通过；非法长度、NaN 和超出审计范围的值会被拒绝。该项分类为 `MATCH`。

它只改变 Observation 到 Policy 的 state 语义，不改变 action、PINK、安全逻辑或机器人控制。
