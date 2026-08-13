#!/usr/bin/env python3
"""CPU-only acceptance tests for the Step 7C.3 float-safe limit logic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from joint_safety_float_limits import evaluate_joint_safety


def run_case(name: str, actual: float, target: float, lower: float, upper: float, expected: str) -> dict:
    decision = evaluate_joint_safety(
        joint_names=["test_joint"],
        joint_actual_source=np.asarray([actual], dtype=np.float32),
        joint_target_source=np.asarray([target], dtype=np.float32),
        joint_lower_source=np.asarray([lower], dtype=np.float32),
        joint_upper_source=np.asarray([upper], dtype=np.float32),
        max_joint_delta_rad=0.05,
    )
    clamp_reason = decision["clamps"][0]["reason"] if decision["clamps"] else None
    observed = clamp_reason or decision["reason_code"]
    passed = observed == expected
    return {"name": name, "expected": expected, "observed": observed, "pass": passed, "decision": decision}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite {args.output}")

    upper = np.float32(0.04)
    lower = np.float32(-0.04)
    upper_one_ulp = np.nextafter(upper, np.float32(np.inf), dtype=np.float32)
    lower_one_ulp = np.nextafter(lower, np.float32(-np.inf), dtype=np.float32)
    upper_real = np.float32(float(upper) + 1e-5)
    lower_real = np.float32(float(lower) - 1e-5)

    cases = [
        run_case("upper_below", 0.0, 0.03, -0.04, upper, "PASS"),
        run_case("upper_equal", 0.0, upper, -0.04, upper, "PASS"),
        run_case("upper_one_ulp", 0.0, upper_one_ulp, -0.04, upper, "FLOAT_TOLERANCE_UPPER_CLAMP"),
        run_case("upper_real_violation", 0.0, upper_real, -0.04, upper, "JOINT_UPPER_LIMIT"),
        run_case("lower_above", 0.0, -0.03, lower, 0.04, "PASS"),
        run_case("lower_equal", 0.0, lower, lower, 0.04, "PASS"),
        run_case("lower_one_ulp", 0.0, lower_one_ulp, lower, 0.04, "FLOAT_TOLERANCE_LOWER_CLAMP"),
        run_case("lower_real_violation", 0.0, lower_real, lower, 0.04, "JOINT_LOWER_LIMIT"),
        run_case("nan_target", 0.0, np.nan, -1.0, 1.0, "NONFINITE_JOINT_TARGET"),
        run_case("positive_inf", 0.0, np.inf, -1.0, 1.0, "NONFINITE_JOINT_TARGET"),
        run_case("negative_inf", 0.0, -np.inf, -1.0, 1.0, "NONFINITE_JOINT_TARGET"),
        run_case("joint_delta_over", 0.0, 0.051, -1.0, 1.0, "JOINT_DELTA_LIMIT"),
        run_case("joint_delta_equal", 0.0, 0.05, -1.0, 1.0, "PASS"),
    ]
    result = {
        "all_pass": all(case["pass"] for case in cases),
        "case_count": len(cases),
        "float32_eps": float(np.finfo(np.float32).eps),
        "upper_limit": float(upper),
        "upper_spacing": float(np.spacing(upper)),
        "upper_one_ulp_excess": float(upper_one_ulp - upper),
        "tolerance_policy": "2 ULP of the coarsest runtime float dtype per joint limit",
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}, indent=2))
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
