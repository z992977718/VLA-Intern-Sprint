#!/usr/bin/env python3
"""Project-side helpers for a seven-DOF Franka PINK arm model.

The upstream Isaac/PINK extension is left untouched.  The two finger joints are
locked out of the Pinocchio model, while Isaac articulation commands keep an
explicit and independent gripper path.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import numpy as np


def write_arm_only_urdf(
    source_urdf: Path | str,
    destination_urdf: Path | str,
    *,
    finger_joint_names: Sequence[str],
) -> dict:
    """Write a project-side arm-only URDF without modifying the bundled file."""

    source_urdf = Path(source_urdf)
    destination_urdf = Path(destination_urdf)
    if destination_urdf.exists():
        raise FileExistsError(f"Refusing to overwrite {destination_urdf}")
    finger_joint_names = list(finger_joint_names)
    tree = ElementTree.parse(source_urdf)
    root = tree.getroot()
    joints = list(root.findall("joint"))
    links = list(root.findall("link"))
    by_name = {joint.get("name"): joint for joint in joints}
    missing = [name for name in finger_joint_names if name not in by_name]
    if missing:
        raise ValueError(f"Finger joints missing from source URDF: {missing}")

    removed_links = {
        by_name[name].find("child").get("link")
        for name in finger_joint_names
    }
    removed_joints = set(finger_joint_names)
    changed = True
    while changed:
        changed = False
        for joint in joints:
            parent = joint.find("parent").get("link")
            child = joint.find("child").get("link")
            if parent in removed_links and joint.get("name") not in removed_joints:
                removed_joints.add(joint.get("name"))
                removed_links.add(child)
                changed = True

    for joint in joints:
        if joint.get("name") in removed_joints:
            root.remove(joint)
    for link in links:
        if link.get("name") in removed_links:
            root.remove(link)

    destination_urdf.parent.mkdir(parents=True, exist_ok=True)
    tree.write(destination_urdf, encoding="utf-8", xml_declaration=True)
    return {
        "source_urdf": str(source_urdf),
        "destination_urdf": str(destination_urdf),
        "removed_joint_names": sorted(removed_joints),
        "removed_link_names": sorted(removed_links),
        "upstream_modified": False,
    }


def articulation_joint_indices(
    articulation_joint_names: Sequence[str],
    requested_joint_names: Sequence[str],
) -> np.ndarray:
    """Resolve a named command space into Isaac articulation indices."""

    names = list(articulation_joint_names)
    requested = list(requested_joint_names)
    if len(set(names)) != len(names):
        raise ValueError("Articulation joint names are not unique")
    missing = [name for name in requested if name not in names]
    if missing:
        raise ValueError(f"Requested joints missing from articulation: {missing}")
    indices = np.asarray([names.index(name) for name in requested], dtype=np.int64)
    if len(set(indices.tolist())) != len(indices):
        raise ValueError("Resolved articulation indices are not unique")
    return indices


def independent_gripper_target(finger_target_m: float) -> np.ndarray:
    """Build the two-finger target without involving PINK."""

    target = np.asarray([finger_target_m, finger_target_m], dtype=np.float32)
    if not np.isfinite(target).all():
        raise ValueError("Gripper target must be finite")
    return target


def compose_articulation_target(
    *,
    current_articulation_q: np.ndarray,
    arm_target: np.ndarray,
    gripper_target: np.ndarray,
    arm_indices: np.ndarray,
    finger_indices: np.ndarray,
) -> np.ndarray:
    """Compose a full vector for auditing only; runtime sends both paths separately."""

    result = np.asarray(current_articulation_q, dtype=np.float64).copy()
    arm_target = np.asarray(arm_target, dtype=np.float64)
    gripper_target = np.asarray(gripper_target, dtype=np.float64)
    arm_indices = np.asarray(arm_indices, dtype=np.int64)
    finger_indices = np.asarray(finger_indices, dtype=np.int64)
    if arm_target.shape != arm_indices.shape:
        raise ValueError("Arm target and index shapes differ")
    if gripper_target.shape != finger_indices.shape:
        raise ValueError("Gripper target and index shapes differ")
    if set(arm_indices.tolist()) & set(finger_indices.tolist()):
        raise ValueError("Arm and gripper command indices overlap")
    result[arm_indices] = arm_target
    result[finger_indices] = gripper_target
    return result
