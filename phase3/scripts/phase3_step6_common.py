#!/usr/bin/env python3
"""Step 6 shared, source-audited scene constants and geometric predicates."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np


PROJECT = Path("/root/autodl-tmp/VLA-Intern-Sprint")
RESULT = PROJECT / "results/phase3_step6"
CHECKPOINT = PROJECT / "results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model"
LANGUAGE = "put both the alphabet soup and the tomato sauce in the basket"
ARM_JOINTS = tuple(f"panda_joint{index}" for index in range(1, 8))
FINGER_JOINTS = ("panda_finger_joint1", "panda_finger_joint2")
JOINT_NAMES = ARM_JOINTS + FINGER_JOINTS
MAX_CYCLES = 100
CONTROL_STEPS_PER_ACTION = 120
PHYSICS_DT = 1.0 / 60.0
# Calibrated from the audited state-0 Isaac panda_hand and LIBERO robot0_eef
# positions. The residual lateral mismatch is < 0.5 mm; orientation is shared.
EEF_OFFSET_IN_HAND_M = np.array([0.0, 0.0, 0.0951034858], dtype=np.float64)

# Source: installed basket.xml. MuJoCo site sizes are half extents.
BASKET_CONTAIN_LOCAL_POSITION = np.array([0.0, 0.0, 0.07185], dtype=np.float64)
BASKET_CONTAIN_LOCAL_QUATERNION_WXYZ = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
BASKET_CONTAIN_HALF_EXTENTS = np.array([0.06108, 0.06108, 0.06949], dtype=np.float64)

# Five collision boxes from the installed basket.xml. Values are local to basket body.
BASKET_COLLIDERS = (
    ([0.00251, 0.0, 0.01308], [0.70880, 0.0, 0.70541, 0.0], [0.00850, 0.07240, 0.07658]),
    ([-0.07265, 0.0, 0.07657], [0.02672, -0.02672, 0.70660, 0.70660], [0.00667, 0.06368, 0.07240]),
    ([0.00047, -0.06855, 0.08177], [0.51263, -0.49025, 0.50956, -0.48704], [0.00667, 0.06368, 0.07240]),
    ([-0.00020, 0.06909, 0.08177], [0.48794, -0.51043, -0.48935, 0.51177], [0.00667, 0.06368, 0.07240]),
    ([0.07557, 0.0, 0.07657], [0.01765, 0.01765, -0.70689, 0.70689], [0.00667, 0.06368, 0.07240]),
)

# Exact LIBERO table-top collider (MuJoCo geom 10), expressed in world coordinates.
TABLE_TOP_POSITION = np.array([-0.25, 0.05239, 0.42492], dtype=np.float64)
TABLE_TOP_QUATERNION_WXYZ = np.array([0.5, -0.5, -0.5, -0.5], dtype=np.float64)
TABLE_TOP_HALF_EXTENTS = np.array([0.01184, 0.44432, 0.67171], dtype=np.float64)

OBJECT_VISUAL_SCALES = {
    "alphabet_soup": (0.01, 0.01, 0.01),
    "tomato_sauce": (0.01, 0.01, 0.01),
    "basket": (1.0, 1.0, 1.0),
    "living_room_table": (1.5, 1.5, 1.5),
}
OBJECT_APPROX_HALF_EXTENTS = {
    "alphabet_soup": np.array([0.03302786, 0.041777305, 0.03556027]),
    "tomato_sauce": np.array([0.03323490, 0.041423355, 0.035099105]),
}
OBJECT_APPROX_CENTERS = {
    "alphabet_soup": np.array([0.0, -0.000177575, -0.00016168]),
    "tomato_sauce": np.array([0.0, -0.000000205, -0.000040845]),
}


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def normalize_quaternion_wxyz(quaternion: np.ndarray) -> np.ndarray:
    quaternion = np.asarray(quaternion, dtype=np.float64)
    norm = float(np.linalg.norm(quaternion))
    if norm < 1e-12:
        raise ValueError("zero quaternion")
    return quaternion / norm


def quaternion_wxyz_to_matrix(quaternion: np.ndarray) -> np.ndarray:
    w, x, y, z = normalize_quaternion_wxyz(quaternion)
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def matrix_to_quaternion_wxyz(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.float64)
    trace = float(np.trace(matrix))
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        result = np.array(
            [0.25 * s, (matrix[2, 1] - matrix[1, 2]) / s,
             (matrix[0, 2] - matrix[2, 0]) / s, (matrix[1, 0] - matrix[0, 1]) / s]
        )
    else:
        index = int(np.argmax(np.diag(matrix)))
        if index == 0:
            s = math.sqrt(1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2]) * 2.0
            result = np.array([(matrix[2, 1] - matrix[1, 2]) / s, 0.25 * s,
                               (matrix[0, 1] + matrix[1, 0]) / s, (matrix[0, 2] + matrix[2, 0]) / s])
        elif index == 1:
            s = math.sqrt(1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2]) * 2.0
            result = np.array([(matrix[0, 2] - matrix[2, 0]) / s, (matrix[0, 1] + matrix[1, 0]) / s,
                               0.25 * s, (matrix[1, 2] + matrix[2, 1]) / s])
        else:
            s = math.sqrt(1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1]) * 2.0
            result = np.array([(matrix[1, 0] - matrix[0, 1]) / s, (matrix[0, 2] + matrix[2, 0]) / s,
                               (matrix[1, 2] + matrix[2, 1]) / s, 0.25 * s])
    return normalize_quaternion_wxyz(result)


def load_libero_reference(initial_state_id: int) -> dict:
    folder = "libero_reference" if initial_state_id == 0 else f"libero_reference_state{initial_state_id:02d}"
    return json.loads((RESULT / folder / "libero_reference.json").read_text(encoding="utf-8"))


def compose_pose(
    parent_position: np.ndarray,
    parent_quaternion_wxyz: np.ndarray,
    local_position: np.ndarray,
    local_quaternion_wxyz: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    parent_rotation = quaternion_wxyz_to_matrix(parent_quaternion_wxyz)
    local_rotation = quaternion_wxyz_to_matrix(local_quaternion_wxyz)
    return (
        np.asarray(parent_position) + parent_rotation @ np.asarray(local_position),
        matrix_to_quaternion_wxyz(parent_rotation @ local_rotation),
    )


def point_in_basket(
    point_world: np.ndarray,
    basket_position: np.ndarray,
    basket_quaternion_wxyz: np.ndarray,
) -> tuple[bool, np.ndarray]:
    site_position, site_quaternion = compose_pose(
        basket_position,
        basket_quaternion_wxyz,
        BASKET_CONTAIN_LOCAL_POSITION,
        BASKET_CONTAIN_LOCAL_QUATERNION_WXYZ,
    )
    site_rotation = quaternion_wxyz_to_matrix(site_quaternion)
    point_local = site_rotation.T @ (np.asarray(point_world, dtype=np.float64) - site_position)
    inside = bool(np.all(np.abs(point_local) <= BASKET_CONTAIN_HALF_EXTENTS + 1e-9))
    return inside, point_local


def task_success(
    soup_center_world: np.ndarray,
    tomato_center_world: np.ndarray,
    basket_position: np.ndarray,
    basket_quaternion_wxyz: np.ndarray,
) -> dict:
    soup_inside, soup_local = point_in_basket(soup_center_world, basket_position, basket_quaternion_wxyz)
    tomato_inside, tomato_local = point_in_basket(tomato_center_world, basket_position, basket_quaternion_wxyz)
    return {
        "alphabet_soup_inside": soup_inside,
        "tomato_sauce_inside": tomato_inside,
        "alphabet_soup_center_in_contain_frame_m": soup_local.tolist(),
        "tomato_sauce_center_in_contain_frame_m": tomato_local.tolist(),
        "success": bool(soup_inside and tomato_inside),
    }


def synthetic_success_tests() -> dict:
    basket_position = np.array([0.1, -0.2, 0.5])
    basket_quaternion = normalize_quaternion_wxyz(np.array([0.9238795325, 0.0, 0.0, 0.3826834324]))
    site_position, site_quaternion = compose_pose(
        basket_position,
        basket_quaternion,
        BASKET_CONTAIN_LOCAL_POSITION,
        BASKET_CONTAIN_LOCAL_QUATERNION_WXYZ,
    )
    site_rotation = quaternion_wxyz_to_matrix(site_quaternion)
    positive_a = site_position.copy()
    positive_b = site_position + site_rotation @ (BASKET_CONTAIN_HALF_EXTENTS * np.array([0.5, -0.5, 0.5]))
    negative = site_position + site_rotation @ np.array([BASKET_CONTAIN_HALF_EXTENTS[0] + 0.01, 0.0, 0.0])
    positive_result = task_success(positive_a, positive_b, basket_position, basket_quaternion)
    negative_result = task_success(positive_a, negative, basket_position, basket_quaternion)
    passed = positive_result["success"] and not negative_result["success"]
    return {
        "pass": bool(passed),
        "positive_case": positive_result,
        "negative_case": negative_result,
        "predicate": "both target body centers lie in basket_1_contain_region oriented box",
        "libero_contact_term": "SiteObjectState.check_contact returns True; no extra contact or stability condition added",
        "half_extents_m": BASKET_CONTAIN_HALF_EXTENTS.tolist(),
    }
