#!/usr/bin/env python3
"""Phase 2 / Step 4：LIBERO OSC_POSE action 到安全 Isaac task-space target。"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SafetyConfig:
    translation_action_limit: float = 0.10
    rotation_action_limit: float = 0.05
    max_joint_step_rad: float = 0.05
    workspace_min_xyz_m: tuple[float, float, float] = (0.20, -0.30, 0.20)
    workspace_max_xyz_m: tuple[float, float, float] = (0.70, 0.30, 0.80)


def axis_angle_to_matrix(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float64)
    angle = float(np.linalg.norm(vector))
    if angle < 1e-12:
        return np.eye(3, dtype=np.float64)
    axis = vector / angle
    x, y, z = axis
    skew = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])
    return np.eye(3) + math.sin(angle) * skew + (1.0 - math.cos(angle)) * (skew @ skew)


def matrix_to_quaternion_wxyz(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.float64)
    trace = float(np.trace(matrix))
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        quat = np.array([0.25 * s, (matrix[2, 1] - matrix[1, 2]) / s,
                         (matrix[0, 2] - matrix[2, 0]) / s, (matrix[1, 0] - matrix[0, 1]) / s])
    else:
        index = int(np.argmax(np.diag(matrix)))
        if index == 0:
            s = math.sqrt(1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2]) * 2.0
            quat = np.array([(matrix[2, 1] - matrix[1, 2]) / s, 0.25 * s,
                             (matrix[0, 1] + matrix[1, 0]) / s, (matrix[0, 2] + matrix[2, 0]) / s])
        elif index == 1:
            s = math.sqrt(1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2]) * 2.0
            quat = np.array([(matrix[0, 2] - matrix[2, 0]) / s, (matrix[0, 1] + matrix[1, 0]) / s,
                             0.25 * s, (matrix[1, 2] + matrix[2, 1]) / s])
        else:
            s = math.sqrt(1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1]) * 2.0
            quat = np.array([(matrix[1, 0] - matrix[0, 1]) / s, (matrix[0, 2] + matrix[2, 0]) / s,
                             (matrix[1, 2] + matrix[2, 1]) / s, 0.25 * s])
    return quat / np.linalg.norm(quat)


def rotation_error_axis_angle(target: np.ndarray, actual: np.ndarray) -> np.ndarray:
    error = np.asarray(target) @ np.asarray(actual).T
    cosine = np.clip((np.trace(error) - 1.0) / 2.0, -1.0, 1.0)
    angle = float(np.arccos(cosine))
    if angle < 1e-8:
        return np.zeros(3)
    axis = np.array([error[2, 1] - error[1, 2], error[0, 2] - error[2, 0], error[1, 0] - error[0, 1]])
    axis /= 2.0 * math.sin(angle)
    return axis * angle


def adapt_libero_action(
    action: np.ndarray,
    current_position: np.ndarray,
    current_orientation: np.ndarray,
    safety: SafetyConfig,
) -> dict:
    """复现 robosuite 1.4 OSC_POSE 缩放和左乘姿态组合，并施加 smoke-test 安全边界。"""
    raw = np.asarray(action, dtype=np.float64)
    if raw.shape != (7,):
        raise ValueError(f"action shape 必须为 (7,), 实际为 {raw.shape}")
    if not np.isfinite(raw).all():
        raise ValueError("action 含 NaN/Inf")

    clipped = raw.copy()
    clipped[:3] = np.clip(clipped[:3], -safety.translation_action_limit, safety.translation_action_limit)
    clipped[3:6] = np.clip(clipped[3:6], -safety.rotation_action_limit, safety.rotation_action_limit)
    clipped[6] = np.clip(clipped[6], -1.0, 1.0)

    # robosuite osc_pose.json: [-1,1] -> translation [-0.05,0.05] m,
    # rotation [-0.5,0.5] rad axis-angle. set_goal_orientation uses R_delta @ R_current.
    translation_delta_m = clipped[:3] * 0.05
    rotation_delta_axis_angle_rad = clipped[3:6] * 0.5
    target_position = np.asarray(current_position, dtype=np.float64) + translation_delta_m
    target_orientation = axis_angle_to_matrix(rotation_delta_axis_angle_rad) @ np.asarray(
        current_orientation, dtype=np.float64
    )

    lower = np.asarray(safety.workspace_min_xyz_m)
    upper = np.asarray(safety.workspace_max_xyz_m)
    if np.any(target_position < lower) or np.any(target_position > upper):
        raise ValueError(f"目标越过 smoke workspace: {target_position.tolist()}")

    return {
        "raw_action": raw.tolist(),
        "bounded_action": clipped.tolist(),
        "translation_delta_m": translation_delta_m.tolist(),
        "rotation_delta_axis_angle_rad": rotation_delta_axis_angle_rad.tolist(),
        "orientation_composition": "R_target = R_delta @ R_current (robosuite set_goal_orientation)",
        "rotation_frame": "world / spatial left-multiplication",
        "target_position_xyz_m": target_position.tolist(),
        "target_orientation_matrix": target_orientation.tolist(),
        "target_quaternion_wxyz": matrix_to_quaternion_wxyz(target_orientation).tolist(),
        "gripper_command": float(clipped[6]),
        "clipping_applied": bool(not np.allclose(raw, clipped)),
    }
