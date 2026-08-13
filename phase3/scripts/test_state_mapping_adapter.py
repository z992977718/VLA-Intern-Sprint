#!/usr/bin/env python3
"""CPU-only checks for the audited Isaac-to-LIBERO finger convention."""

from __future__ import annotations

import numpy as np

from state_mapping_adapter import build_libero_state_sources, map_isaac_fingers_to_libero_qpos


def main() -> int:
    for source, expected in (
        ([0.04, 0.04], [0.04, -0.04]),
        ([0.02, 0.02], [0.02, -0.02]),
        ([0.0, 0.0], [0.0, 0.0]),
    ):
        actual = map_isaac_fingers_to_libero_qpos(np.asarray(source, dtype=np.float32))
        np.testing.assert_allclose(actual, expected, atol=1e-7)
    for invalid in ([0.02], [0.02, float("nan")], [-0.01, 0.02], [0.05, 0.05]):
        try:
            map_isaac_fingers_to_libero_qpos(np.asarray(invalid, dtype=np.float32))
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected ValueError for {invalid}")
    sources = build_libero_state_sources(
        np.asarray([0.1, -0.2, 0.8], dtype=np.float32),
        np.asarray([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
        np.asarray([0.02, 0.02], dtype=np.float32),
        "/World/Robot/panda_hand/tool_center",
    )
    np.testing.assert_allclose(sources["eef_position_xyz_m"], [0.1, -0.2, 0.8])
    np.testing.assert_allclose(sources["gripper_qpos"], [0.02, -0.02])
    try:
        build_libero_state_sources(
            np.asarray([0.1, -0.2, 0.8], dtype=np.float32),
            np.asarray([0.0, 0.0, 0.0, 1.0], dtype=np.float32),
            np.asarray([0.02, 0.02], dtype=np.float32),
            "/World/Robot/panda_hand",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Expected old panda_hand source to be rejected")
    print("PASS: tool-center state source, open/intermediate/closed, and invalid-input checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
