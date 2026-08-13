# Phase 3 / Step 7B State Mapping / EEF Calibration Audit

## Scope

This is an offline analysis of two static five-pose captures. It did not start Isaac, LIBERO, Pi0.5, training, or a task rollout.

## Measured result

- Five explicitly identical Panda arm joint vectors were assigned independently in LIBERO and Isaac.
- Direct Isaac tool-point to LIBERO EEF position error: mean 37.870 mm, max 70.814 mm.
- A free rigid registration reduces the position residual to mean 37.142 mm, max 63.719 mm. This is diagnostic evidence only, not a runtime mapping to apply.
- Raw Isaac hand to LIBERO policy-source `robot0_eef_quat` orientation error: mean 0.433953 rad, max 0.861912 rad.
- The direct orientation comparison is the relevant one because `LiberoProcessorStep` converts `robot0_eef_quat`, not `controller.ee_ori_mat`, into Pi0.5's state.
- The 95.1035 mm point offset is implemented as `R_hand @ offset_local`; its five-pose formula residual is at numerical precision. A world-fixed offset bug is not confirmed.
- Gripper open/intermediate/closed progression agrees semantically, but LIBERO's mirrored-sign qpos values and Isaac's equal-positive finger values are not numerically interchangeable.
- Recorded maximum image-to-joint skew is 0.15 s for the prior RTX 5090 migration smoke and remains a separate timing limitation.

## Classification

Position semantics: MISMATCH  
Orientation semantics: APPROXIMATE (policy-source quaternion)  
Tool-point calibration: APPROXIMATE  
Gripper state: MISMATCH  
Time synchronization: POTENTIAL ISSUE  
Overall State Mapping: MISMATCH

## Decision

The current State Adapter uses the corrected tool point for position and raw `panda_hand` orientation for state. The policy-source orientation comparison is only APPROXIMATE and does not justify a simple fixed rotation. Direct position correspondence and gripper numeric conventions are non-equivalent. Preserve these files as before-fix evidence. The only recommended next step is **A. Fix State Mapping and rerun calibration**, after explicit approval. No correction was applied in this audit.
