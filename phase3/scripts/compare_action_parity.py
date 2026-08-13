#!/usr/bin/env python3
"""Compare Step 7A LIBERO and Isaac measurements without inventing thresholds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


TRANSLATION = ("+X", "-X", "+Y", "-Y", "+Z", "-Z")
ROTATION = ("+Rx", "-Rx", "+Ry", "-Ry", "+Rz", "-Rz")
GRIPPER = ("open", "close")


def classify_translation(left: dict, right: dict) -> tuple[str, dict]:
    a, b = np.asarray(left["actual_delta_xyz_m"]), np.asarray(right["actual_delta_xyz_m"])
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    cosine = None if na < 1e-8 or nb < 1e-8 else float(np.dot(a, b) / (na * nb))
    axes_match = None if cosine is None else bool(cosine > 0.95)
    ratio = None if na < 1e-8 else nb / na
    if cosine is not None and cosine > 0.95 and 0.5 <= ratio <= 2.0: status = "MATCH"
    elif cosine is not None and cosine > 0.75: status = "APPROXIMATE"
    else: status = "MISMATCH"
    return status, {"direction_cosine": cosine, "libero_magnitude_m": na, "isaac_magnitude_m": nb, "isaac_over_libero_magnitude_ratio": ratio, "dominant_axis_direction_consistent": axes_match}


def classify_rotation(left: dict, right: dict) -> tuple[str, dict]:
    a, b = np.asarray(left["relative_rotation_axis_angle_rad"]), np.asarray(right["relative_rotation_axis_angle_rad"])
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    cosine = None if na < 1e-8 or nb < 1e-8 else float(np.dot(a, b) / (na * nb))
    ratio = None if na < 1e-8 else nb / na
    if cosine is not None and cosine > 0.95 and 0.5 <= ratio <= 2.0: status = "MATCH"
    elif cosine is not None and cosine > 0.75: status = "APPROXIMATE"
    else: status = "MISMATCH"
    return status, {"axis_sign_cosine": cosine, "libero_magnitude_rad": na, "isaac_magnitude_rad": nb, "isaac_over_libero_magnitude_ratio": ratio}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--dir", type=Path, required=True); args = parser.parse_args()
    root = args.dir.resolve()
    libero = json.loads((root / "libero_all.json").read_text())["cases"]
    isaac = {path.stem.removeprefix("isaac_"): json.loads(path.read_text()) for path in root.glob("isaac_*.json")}
    if set(libero) != set(isaac): raise RuntimeError(f"case set mismatch: libero={sorted(libero)}, isaac={sorted(isaac)}")
    translations = {}; rotations = {}; grippers = {}
    for name in TRANSLATION:
        status, metrics = classify_translation(libero[name], isaac[name]); translations[name] = {"status": status, **metrics}
    for name in ROTATION:
        status, metrics = classify_rotation(libero[name], isaac[name]); rotations[name] = {"status": status, **metrics}
    for name in GRIPPER:
        same = libero[name]["gripper_semantic"] == isaac[name]["gripper_semantic"]
        grippers[name] = {"status": "MATCH" if same else "MISMATCH", "libero_semantic": libero[name]["gripper_semantic"], "isaac_semantic": isaac[name]["gripper_semantic"]}
    matrix = {**translations, **rotations, **grippers}
    final = "MISMATCH" if any(x["status"] == "MISMATCH" for x in matrix.values()) else ("APPROXIMATE" if any(x["status"] == "APPROXIMATE" for x in matrix.values()) else "MATCH")
    (root / "translation_comparison.json").write_text(json.dumps(translations, indent=2) + "\n")
    (root / "rotation_comparison.json").write_text(json.dumps(rotations, indent=2) + "\n")
    (root / "gripper_comparison.json").write_text(json.dumps(grippers, indent=2) + "\n")
    (root / "parity_matrix.json").write_text(json.dumps({"final_action_mapping": final, "cases": matrix, "criteria": "MATCH requires direction/sign agreement and 0.5-2.0 actual-magnitude ratio after one 0.05 s control period; APPROXIMATE retains direction/sign but has tracking/scaling variation; MISMATCH indicates axis/sign/semantic error or no comparable motion."}, indent=2) + "\n")
    for name, cases in (("libero_translation.json", {k: libero[k] for k in TRANSLATION}), ("libero_rotation.json", {k: libero[k] for k in ROTATION}), ("libero_gripper.json", {k: libero[k] for k in GRIPPER}), ("isaac_translation.json", {k: isaac[k] for k in TRANSLATION}), ("isaac_rotation.json", {k: isaac[k] for k in ROTATION}), ("isaac_gripper.json", {k: isaac[k] for k in GRIPPER})):
        (root / name).write_text(json.dumps(cases, indent=2) + "\n")
    return 0


if __name__ == "__main__": raise SystemExit(main())
