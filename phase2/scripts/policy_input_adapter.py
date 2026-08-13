#!/usr/bin/env python3
"""Phase 2 Step 3: adapt one saved Isaac/ROS 2 observation for the real pi0.5 processor.

This module only constructs policy input. It has no ROS publisher, controller,
or action execution code.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image

from lerobot.envs.utils import preprocess_observation
from lerobot.processor.env_processor import LiberoProcessorStep

try:
    from state_mapping_adapter import build_libero_state_sources
except ImportError:
    # Phase 2 remains independently usable; Phase 3 adds its script directory
    # to PYTHONPATH and supplies the source-audited mapping helper.
    def build_libero_state_sources(
        tool_center_position_xyz_m: np.ndarray,
        tool_center_quaternion_xyzw: np.ndarray,
        isaac_finger_qpos: np.ndarray,
        source_prim: str | None = None,
    ) -> dict[str, np.ndarray]:
        if source_prim is not None and not source_prim.rstrip("/").endswith("/tool_center"):
            raise ValueError(
                "State mapping fix requires an Isaac native tool_center pose; "
                f"received {source_prim!r}"
            )
        values = np.asarray(finger_qpos, dtype=np.float32)
        if values.shape != (2,) or not np.isfinite(values).all():
            raise ValueError(f"Expected two finite Isaac finger positions, got {values!r}")
        return {
            "eef_position_xyz_m": np.asarray(tool_center_position_xyz_m, dtype=np.float32),
            "eef_quaternion_xyzw": np.asarray(tool_center_quaternion_xyzw, dtype=np.float32),
            "gripper_qpos": np.array([values[0], -values[1]], dtype=np.float32),
        }


ARM_JOINTS = tuple(f"panda_joint{index}" for index in range(1, 8))
FINGER_JOINTS = ("panda_finger_joint1", "panda_finger_joint2")


def _finite_vector(values: list[float], expected_length: int, label: str) -> np.ndarray:
    vector = np.asarray(values, dtype=np.float32)
    if vector.shape != (expected_length,):
        raise ValueError(f"{label} must have shape {(expected_length,)}, got {vector.shape}")
    if not np.isfinite(vector).all():
        raise ValueError(f"{label} contains NaN or Inf")
    return vector


def _load_rgb(path: Path) -> np.ndarray:
    image = np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8).copy()
    if image.shape != (256, 256, 3):
        raise ValueError(f"Expected RGB HWC 256x256 at {path}, got {image.shape}")
    return image


def build_policy_input(result_dir: Path, language: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build canonical policy input using LeRobot's real observation and LIBERO processors."""
    joint_state = json.loads((result_dir / "joint_state.json").read_text(encoding="utf-8"))
    eef_pose = json.loads((result_dir / "eef_pose.json").read_text(encoding="utf-8"))
    positions = joint_state["position_by_name"]

    missing = [name for name in (*ARM_JOINTS, *FINGER_JOINTS) if positions.get(name) is None]
    if missing:
        raise ValueError(f"Missing named Isaac Franka joint positions: {missing}")

    arm_positions = _finite_vector([positions[name] for name in ARM_JOINTS], 7, "arm joints")
    isaac_finger_qpos = _finite_vector([positions[name] for name in FINGER_JOINTS], 2, "finger joints")
    eef_position = _finite_vector(eef_pose["position_xyz_m"], 3, "EEF position")
    eef_quaternion_xyzw = _finite_vector(eef_pose["quaternion_xyzw"], 4, "EEF quaternion")
    quaternion_norm = float(np.linalg.norm(eef_quaternion_xyzw))
    if not math.isclose(quaternion_norm, 1.0, rel_tol=0.0, abs_tol=1e-5):
        raise ValueError(f"EEF quaternion is not normalized: norm={quaternion_norm}")
    state_sources = build_libero_state_sources(
        eef_position, eef_quaternion_xyzw, isaac_finger_qpos, eef_pose.get("source_prim")
    )
    eef_position = state_sources["eef_position_xyz_m"]
    eef_quaternion_xyzw = state_sources["eef_quaternion_xyzw"]
    gripper_qpos = state_sources["gripper_qpos"]

    external_rgb = _load_rgb(result_dir / "camera_external.png")
    wrist_rgb = _load_rgb(result_dir / "camera_wrist.png")
    raw_observation = {
        "pixels": {
            "image": external_rgb,
            "image2": wrist_rgb,
        },
        "robot_state": {
            "eef": {
                "pos": eef_position[None, :],
                "quat": eef_quaternion_xyzw[None, :],
            },
            "gripper": {
                "qpos": gripper_qpos[None, :],
            },
            "joints": {
                "pos": arm_positions[None, :],
            },
        },
    }

    # These are the exact two LeRobot steps used in LIBERO rollout before the
    # checkpoint-owned pi0.5 preprocessor: numpy/HWC -> tensor/BCHW, then
    # LiberoProcessorStep image flip and state construction/quaternion conversion.
    observation = preprocess_observation(raw_observation)
    observation["task"] = [language]
    observation = LiberoProcessorStep().observation(observation)

    expected_keys = {
        "observation.images.image",
        "observation.images.image2",
        "observation.state",
        "task",
    }
    missing_policy_keys = sorted(expected_keys - set(observation))
    if missing_policy_keys:
        raise ValueError(f"Missing canonical policy input keys: {missing_policy_keys}")
    if tuple(observation["observation.state"].shape) != (1, 8):
        raise ValueError(f"Expected 8D batched state, got {observation['observation.state'].shape}")

    state = observation["observation.state"][0].detach().cpu().numpy()
    sample = {
        "source_joint_topic": joint_state["topic"],
        "source_joint_order": list(joint_state["raw_order"]),
        "arm_joint_order": list(ARM_JOINTS),
        "arm_joint_positions_rad": arm_positions.tolist(),
        "eef_source_prim": eef_pose["source_prim"],
        "eef_source_semantic_requirement": "native Isaac tool_center pose; old panda_hand-derived records are intentionally rejected after Step 7B.1",
        "eef_reference_frame": eef_pose["reference_frame"],
        "eef_position_unit": eef_pose["position_unit"],
        "eef_position_xyz_m": eef_position.tolist(),
        "eef_quaternion_source_wxyz": eef_pose["quaternion_wxyz"],
        "eef_quaternion_target_xyzw": eef_quaternion_xyzw.tolist(),
        "eef_axis_angle_rad": state[3:6].tolist(),
        "gripper_joint_order": list(FINGER_JOINTS),
        "gripper_qpos_source_values": isaac_finger_qpos.tolist(),
        "gripper_qpos_libero_compatible_values": gripper_qpos.tolist(),
        "gripper_semantic_compatibility": "MAPPED: Isaac [finger1, finger2] is converted to LIBERO-compatible [finger1, -finger2] from Panda joint axis semantics and cached dataset distribution audit",
        "phase1_state_order": [
            "eef_x_m",
            "eef_y_m",
            "eef_z_m",
            "eef_axis_angle_x_rad",
            "eef_axis_angle_y_rad",
            "eef_axis_angle_z_rad",
            "gripper_qpos_0",
            "gripper_qpos_1",
        ],
        "robot_state_8d": state.tolist(),
        "finite": bool(np.isfinite(state).all()),
        "language": language,
    }
    return observation, sample
