#!/usr/bin/env python3
"""CPU-only A-G acceptance tests for Step 7C.5."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pinocchio as pin

from phase3_step6_common import ARM_JOINTS, FINGER_JOINTS, JOINT_NAMES
from pink_arm_only import (
    articulation_joint_indices,
    compose_articulation_target,
    independent_gripper_target,
    write_arm_only_urdf,
)


def dump(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--safety-results", type=Path, required=True)
    args = parser.parse_args()
    if not args.urdf.is_file():
        raise FileNotFoundError(args.urdf)
    if not args.result_dir.is_dir():
        raise FileNotFoundError(args.result_dir)
    if any((args.result_dir / name).exists() for name in (
        "before_fix_architecture.json", "after_fix_architecture.json", "joint_mapping.json", "unit_tests.json"
    )):
        raise FileExistsError("Refusing to overwrite Step 7C.5 unit-test artifacts")

    full_model = pin.buildModelFromUrdf(str(args.urdf))
    full_names = [full_model.names[i] for i in range(1, full_model.njoints) if full_model.joints[i].nq > 0]
    generated_urdf = args.result_dir / "franka_arm_only.urdf"
    urdf_change = write_arm_only_urdf(
        args.urdf,
        generated_urdf,
        finger_joint_names=FINGER_JOINTS,
    )
    reduced_model = pin.buildModelFromUrdf(str(generated_urdf))
    reduced_names = [
        reduced_model.names[i]
        for i in range(1, reduced_model.njoints)
        if reduced_model.joints[i].nq > 0
    ]

    arm_indices = articulation_joint_indices(JOINT_NAMES, ARM_JOINTS)
    finger_indices = articulation_joint_indices(JOINT_NAMES, FINGER_JOINTS)
    arm_target = np.asarray([0.11, -0.22, 0.33, -0.44, 0.55, -0.66, 0.77], dtype=np.float64)
    gripper_target = independent_gripper_target(0.04)
    combined = compose_articulation_target(
        current_articulation_q=np.zeros(len(JOINT_NAMES), dtype=np.float64),
        arm_target=arm_target,
        gripper_target=gripper_target,
        arm_indices=arm_indices,
        finger_indices=finger_indices,
    )
    safety = json.loads(args.safety_results.read_text(encoding="utf-8"))
    tests = {
        "A_pink_configuration_dimension_7": reduced_model.nq == 7 and reduced_model.nv == 7,
        "B_controlled_joints_exactly_arm": reduced_names == list(ARM_JOINTS),
        "C_finger1_absent": FINGER_JOINTS[0] not in reduced_names and FINGER_JOINTS[0] not in list(reduced_model.names),
        "D_finger2_absent": FINGER_JOINTS[1] not in reduced_names and FINGER_JOINTS[1] not in list(reduced_model.names),
        "E_arm_mapping_exact": arm_indices.tolist() == list(range(7)),
        "F_independent_gripper_target": gripper_target.tolist() == [0.03999999910593033, 0.03999999910593033],
        "G_final_mapping_no_shift": np.allclose(combined[:7], arm_target) and np.allclose(combined[7:], gripper_target),
        "H_safety_regression_13_of_13": bool(safety.get("all_pass")) and safety.get("case_count") == 13,
    }
    all_pass = all(tests.values())

    before = {
        "status": "CONFIRMED_FROM_INSTALLED_BUNDLED_URDF",
        "model_nq": full_model.nq,
        "model_nv": full_model.nv,
        "controlled_joint_names": full_names,
        "finger_included": any(name in full_names for name in FINGER_JOINTS),
        "panda_hand_frame_present": full_model.existFrame("panda_hand"),
        "source_urdf": str(args.urdf),
    }
    after = {
        "status": "CPU_STATIC_TESTED",
        "construction": "project-side generated URDF removes both finger subtrees; bundled upstream URDF is unchanged",
        "model_nq": reduced_model.nq,
        "model_nv": reduced_model.nv,
        "controlled_joint_names": reduced_names,
        "finger_included": any(name in reduced_names for name in FINGER_JOINTS),
        "panda_hand_frame_present": reduced_model.existFrame("panda_hand"),
        "posture_dimension": reduced_model.nq,
        "velocity_dimension": reduced_model.nv,
        "generated_urdf": str(generated_urdf),
        "urdf_change": urdf_change,
    }
    mapping = {
        "pink_arm_index_to_isaac": [
            {"pink_index": i, "joint_name": name, "isaac_articulation_index": int(arm_indices[i])}
            for i, name in enumerate(ARM_JOINTS)
        ],
        "gripper_only": [
            {"gripper_index": i, "joint_name": name, "isaac_articulation_index": int(finger_indices[i])}
            for i, name in enumerate(FINGER_JOINTS)
        ],
        "arm_and_gripper_indices_overlap": bool(set(arm_indices.tolist()) & set(finger_indices.tolist())),
        "runtime_command_policy": "send 7D arm and 2D gripper targets through separate Isaac selected-index calls",
    }
    unit = {
        "all_pass": all_pass,
        "isaac_started": False,
        "gpu_required": False,
        "tests": tests,
        "safety_regression_source": str(args.safety_results),
    }
    dump(args.result_dir / "before_fix_architecture.json", before)
    dump(args.result_dir / "after_fix_architecture.json", after)
    dump(args.result_dir / "joint_mapping.json", mapping)
    dump(args.result_dir / "unit_tests.json", unit)
    print(json.dumps(unit, indent=2))
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
