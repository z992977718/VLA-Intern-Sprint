# Phase 3 / Step 7C.6：Tomato 固定协议解耦后验证

## 结论

- Step 7C.6：`PASS`
- Tomato formal post-decoupling：`3/3`
- Tomato post-decoupling validation：`ROBUST PASS`
- 当前 basic robot-side scripted Oracle pipeline：`ROBUST PASS`
- 历史 original Tomato：`0/3`，保留不变，属于修复前结果
- 历史 Alphabet：`3/3`

## 固定协议

三个 trial 均为独立 hard reset，使用相同 tomato asset、initial state 0、scene、pre-grasp、descent、grasp、close、lift、hold、physics、PINK cost、OSQP、Safety 和 success metric。唯一继承的修复是 7D arm-only PINK、独立 gripper control，以及 Step 7C.3 已验证的 floating-point-safe Safety。

运行前后对 Oracle、Safety、scene、common config、arm-only helper/URDF 和已安装 PINK controller 计算 SHA-256；哈希 diff 为 0 字节。

## Trial 结果

| Trial | Pre-grasp | Descent | Close | Object motion | Lift | Max Z | Final Z | PINK/Safety failure | Result |
|---|---|---|---|---|---|---:|---:|---|---|
| 00 | PASS | 200/200 | YES | YES | SUCCESS | 146.531 mm | 145.893 mm | NONE | SUCCESS |
| 01 | PASS | 200/200 | YES | YES | SUCCESS | 146.531 mm | 145.893 mm | NONE | SUCCESS |
| 02 | PASS | 200/200 | YES | YES | SUCCESS | 146.531 mm | 145.893 mm | NONE | SUCCESS |

三次 runtime PINK 均为 `nq=nv=7`，finger 不在 PINK configuration。没有 finger configuration-limit failure、IK failure、Safety violation、OOM 或补跑。每个 trial 的最终 finger1/finger2 为约 `0.035155/0.035180 m`。

没有 contact sensor，因此不声称 direct contact measured；这里只依据真实物体位姿变化描述 `object motion / grasp-lift behavior observed`。

## Before / Diagnosis / Fix / After

```text
BEFORE: Alphabet 3/3, Tomato 0/3
  -> floating-point Safety false positive
  -> 2-ULP Safety fix, 13/13 regression PASS
  -> new PINK finger configuration-limit blocker
  -> static audit confirms finger joints incorrectly included in arm IK
  -> 9D arm+finger -> 7D arm-only, gripper independent
  -> one diagnostic SUCCESS, NOT COUNTED
  -> FORMAL AFTER: Tomato 3/3, ROBUST PASS
```

## 解释边界

本实验完全没有使用 Pi0.5。它证明已确认的 basic robot-side scripted manipulation blockers 在当前固定协议中已经清除并通过三次一致验证，但不能证明 Step 6 Pi0.5 `0/3` 是由这些问题造成，也不代表 Pi0.5 success、LIBERO transfer、跨域泛化或真实机器人部署。

推荐下一步是获得新授权后只运行一次 `ONE_POST_STATE_MAPPING_PI05_DIAGNOSTIC_ROLLOUT`。本阶段没有执行该下一步。
