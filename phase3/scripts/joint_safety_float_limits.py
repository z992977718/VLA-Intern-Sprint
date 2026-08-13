#!/usr/bin/env python3
"""Pure NumPy joint-safety evaluation with dtype-aware limit clamping."""

from __future__ import annotations

import numpy as np


LIMIT_TOLERANCE_ULPS = 2


def _coarsest_float_dtype(*arrays: np.ndarray) -> np.dtype:
    dtypes = [np.asarray(array).dtype for array in arrays]
    float_dtypes = [dtype for dtype in dtypes if np.issubdtype(dtype, np.floating)]
    if not float_dtypes:
        return np.dtype(np.float64)
    return min(float_dtypes, key=lambda dtype: dtype.itemsize)


def _limit_tolerance(lower: np.ndarray, upper: np.ndarray, dtype: np.dtype) -> np.ndarray:
    lower_typed = np.asarray(lower, dtype=dtype)
    upper_typed = np.asarray(upper, dtype=dtype)
    lower_ulp = np.abs(np.spacing(lower_typed)).astype(np.float64)
    upper_ulp = np.abs(np.spacing(upper_typed)).astype(np.float64)
    return LIMIT_TOLERANCE_ULPS * np.maximum(lower_ulp, upper_ulp)


def _finite_list(array: np.ndarray) -> list[float | None]:
    return [float(value) if np.isfinite(value) else None for value in np.asarray(array, dtype=np.float64)]


def evaluate_joint_safety(
    *,
    joint_names: list[str] | tuple[str, ...],
    joint_actual_source: np.ndarray,
    joint_target_source: np.ndarray,
    joint_lower_source: np.ndarray,
    joint_upper_source: np.ndarray,
    max_joint_delta_rad: float,
) -> dict:
    """Evaluate finite/delta/limit safety and clamp only within two source-dtype ULPs."""

    actual_source = np.asarray(joint_actual_source)
    target_source = np.asarray(joint_target_source)
    lower_source = np.asarray(joint_lower_source)
    upper_source = np.asarray(joint_upper_source)
    if not (actual_source.shape == target_source.shape == lower_source.shape == upper_source.shape):
        raise ValueError("joint safety arrays must have identical shapes")
    if len(joint_names) != target_source.size:
        raise ValueError("joint_names length does not match joint arrays")

    comparison_dtype = _coarsest_float_dtype(actual_source, target_source, lower_source, upper_source)
    actual = actual_source.astype(np.float64)
    raw_target = target_source.astype(np.float64)
    lower = lower_source.astype(np.float64)
    upper = upper_source.astype(np.float64)
    tolerance = _limit_tolerance(lower, upper, comparison_dtype)

    delta = raw_target - actual
    abs_delta = np.abs(delta)
    finite_actual = np.isfinite(actual)
    finite_target = np.isfinite(raw_target)
    finite_limits = np.isfinite(lower) & np.isfinite(upper)
    typed_delta_threshold = float(np.asarray(max_joint_delta_rad, dtype=comparison_dtype))
    delta_violation = finite_actual & finite_target & (abs_delta > typed_delta_threshold)
    real_lower_violation = finite_target & finite_limits & (raw_target < lower - tolerance)
    real_upper_violation = finite_target & finite_limits & (raw_target > upper + tolerance)
    lower_clamp = finite_target & finite_limits & ~real_lower_violation & (raw_target < lower)
    upper_clamp = finite_target & finite_limits & ~real_upper_violation & (raw_target > upper)

    clamped_target = raw_target.copy()
    clamped_target[lower_clamp] = lower[lower_clamp]
    clamped_target[upper_clamp] = upper[upper_clamp]

    per_joint = []
    clamps = []
    violations = []
    for index, name in enumerate(joint_names):
        row = {
            "name": str(name),
            "index": index,
            "actual": float(actual[index]) if finite_actual[index] else None,
            "raw_target": float(raw_target[index]) if finite_target[index] else None,
            "clamped_target": float(clamped_target[index]) if np.isfinite(clamped_target[index]) else None,
            "delta": float(delta[index]) if np.isfinite(delta[index]) else None,
            "abs_delta": float(abs_delta[index]) if np.isfinite(abs_delta[index]) else None,
            "lower": float(lower[index]) if np.isfinite(lower[index]) else None,
            "upper": float(upper[index]) if np.isfinite(upper[index]) else None,
            "tolerance": float(tolerance[index]),
            "lower_margin_raw": float(raw_target[index] - lower[index]) if finite_target[index] else None,
            "upper_margin_raw": float(upper[index] - raw_target[index]) if finite_target[index] else None,
            "finite_actual": bool(finite_actual[index]),
            "finite_target": bool(finite_target[index]),
            "finite_limits": bool(finite_limits[index]),
            "delta_violation": bool(delta_violation[index]),
            "real_lower_violation": bool(real_lower_violation[index]),
            "real_upper_violation": bool(real_upper_violation[index]),
            "lower_clamp": bool(lower_clamp[index]),
            "upper_clamp": bool(upper_clamp[index]),
        }
        per_joint.append(row)
        if lower_clamp[index]:
            clamps.append(
                {
                    "reason": "FLOAT_TOLERANCE_LOWER_CLAMP",
                    "joint": str(name),
                    "index": index,
                    "raw_target": float(raw_target[index]),
                    "limit": float(lower[index]),
                    "excess": float(lower[index] - raw_target[index]),
                    "tolerance": float(tolerance[index]),
                    "clamped_target": float(clamped_target[index]),
                }
            )
        if upper_clamp[index]:
            clamps.append(
                {
                    "reason": "FLOAT_TOLERANCE_UPPER_CLAMP",
                    "joint": str(name),
                    "index": index,
                    "raw_target": float(raw_target[index]),
                    "limit": float(upper[index]),
                    "excess": float(raw_target[index] - upper[index]),
                    "tolerance": float(tolerance[index]),
                    "clamped_target": float(clamped_target[index]),
                }
            )

    def selected(mask: np.ndarray) -> list[dict]:
        return [per_joint[index] for index in np.flatnonzero(mask)]

    if not finite_actual.all() or not finite_target.all() or not finite_limits.all():
        violations.append({"code": "NONFINITE_JOINT_TARGET", "joints": selected(~finite_target | ~finite_limits)})
    if delta_violation.any():
        violations.append(
            {
                "code": "JOINT_DELTA_LIMIT",
                "threshold_rad": max_joint_delta_rad,
                "joints": selected(delta_violation),
            }
        )
    if real_lower_violation.any():
        violations.append({"code": "JOINT_LOWER_LIMIT", "joints": selected(real_lower_violation)})
    if real_upper_violation.any():
        violations.append({"code": "JOINT_UPPER_LIMIT", "joints": selected(real_upper_violation)})

    reason_code = "PASS"
    if len(violations) == 1:
        reason_code = violations[0]["code"]
    elif len(violations) > 1:
        reason_code = "MULTIPLE_SAFETY_VIOLATIONS"
    max_delta_index = int(np.nanargmax(abs_delta)) if np.isfinite(abs_delta).any() else None
    return {
        "pass": not violations,
        "reason_code": reason_code,
        "comparison_dtype": str(comparison_dtype),
        "target_source_dtype": str(target_source.dtype),
        "limit_source_dtype": str(lower_source.dtype),
        "tolerance_policy": f"{LIMIT_TOLERANCE_ULPS} ULP of the coarsest runtime float dtype per joint limit",
        "max_joint_delta_rad": float(max_joint_delta_rad),
        "typed_delta_threshold_rad": typed_delta_threshold,
        "max_abs_joint_delta": float(abs_delta[max_delta_index]) if max_delta_index is not None else None,
        "max_delta_joint": str(joint_names[max_delta_index]) if max_delta_index is not None else None,
        "raw_target": _finite_list(raw_target),
        "clamped_target": _finite_list(clamped_target),
        "clamps": clamps,
        "violations": violations,
        "per_joint": per_joint,
    }
