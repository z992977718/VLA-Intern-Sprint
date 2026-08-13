#!/usr/bin/env python3
"""Minimal, source-audited Isaac to LIBERO state mapping helpers.

The caller must provide Isaac's native ``tool_center`` world pose. This module
does not infer a world-space correction, control the robot, or call Pi0.5.
"""

from __future__ import annotations

import numpy as np


def map_isaac_fingers_to_libero_qpos(finger_qpos: np.ndarray) -> np.ndarray:
    """Map equal-positive Isaac Panda finger travel to LIBERO's mirrored qpos."""
    values = np.asarray(finger_qpos, dtype=np.float32)
    if values.shape != (2,) or not np.isfinite(values).all():
        raise ValueError(f"Expected two finite Isaac finger positions, got {values!r}")
    if np.any(values < -1e-5) or np.any(values > 0.0401):
        raise ValueError(f"Isaac finger qpos is outside the audited [0, 0.04] range: {values!r}")
    return np.array([values[0], -values[1]], dtype=np.float32)


def build_libero_state_sources(
    tool_center_position_xyz_m: np.ndarray,
    tool_center_quaternion_xyzw: np.ndarray,
    isaac_finger_qpos: np.ndarray,
    source_prim: str | None = None,
) -> dict[str, np.ndarray]:
    """Return the three raw sources expected by ``LiberoProcessorStep``."""
    if source_prim is not None and not source_prim.rstrip("/").endswith("/tool_center"):
        raise ValueError(
            "State mapping fix requires an Isaac native tool_center pose; "
            f"received {source_prim!r}"
        )
    position = np.asarray(tool_center_position_xyz_m, dtype=np.float32)
    quaternion = np.asarray(tool_center_quaternion_xyzw, dtype=np.float32)
    if position.shape != (3,) or not np.isfinite(position).all():
        raise ValueError("tool_center position must be a finite 3D world vector")
    if quaternion.shape != (4,) or not np.isfinite(quaternion).all():
        raise ValueError("tool_center quaternion must be a finite xyzw vector")
    if not np.isclose(float(np.linalg.norm(quaternion)), 1.0, atol=1e-5):
        raise ValueError("tool_center quaternion must be normalized")
    return {
        "eef_position_xyz_m": position,
        "eef_quaternion_xyzw": quaternion,
        "gripper_qpos": map_isaac_fingers_to_libero_qpos(isaac_finger_qpos),
    }
