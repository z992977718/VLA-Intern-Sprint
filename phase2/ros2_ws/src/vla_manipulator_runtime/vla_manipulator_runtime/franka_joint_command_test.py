#!/usr/bin/env python3
"""发布安全 Franka 关节目标，并验证 /joint_states 的闭环变化。"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


ARM_JOINTS = [f"panda_joint{i}" for i in range(1, 8)]
TARGET = [0.0, -0.45, 0.0, -1.75, 0.0, 1.30, 0.78]
RESULT_DIR = Path("/root/autodl-tmp/VLA-Intern-Sprint/results/phase2_step1")


class FrankaJointCommandTest(Node):
    def __init__(self) -> None:
        super().__init__("franka_joint_command_test")
        self.publisher = self.create_publisher(JointState, "/joint_command", 10)
        self.subscription = self.create_subscription(JointState, "/joint_states", self.on_state, 10)
        self.initial: dict[str, float] | None = None
        self.latest: dict[str, float] | None = None
        self.started = time.monotonic()
        self.command_started: float | None = None
        self.done = False
        self.timer = self.create_timer(0.1, self.tick)

    def on_state(self, msg: JointState) -> None:
        values = dict(zip(msg.name, msg.position, strict=False))
        if not all(name in values for name in ARM_JOINTS):
            return
        state = {name: float(values[name]) for name in ARM_JOINTS}
        self.latest = state
        if self.initial is None:
            self.initial = state.copy()
            RESULT_DIR.mkdir(parents=True, exist_ok=True)
            (RESULT_DIR / "joint_state_before.json").write_text(
                json.dumps({"timestamp": time.time(), "positions": state}, indent=2), encoding="utf-8"
            )
            self.get_logger().info(f"INITIAL_STATE={json.dumps(state)}")

    def tick(self) -> None:
        elapsed = time.monotonic() - self.started
        if self.initial is None:
            if elapsed > 30:
                raise RuntimeError("30 秒内未收到 /joint_states")
            return

        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = ARM_JOINTS
        msg.position = TARGET
        self.publisher.publish(msg)
        if self.command_started is None:
            self.command_started = time.monotonic()
            self.get_logger().info(f"TARGET_STATE={json.dumps(dict(zip(ARM_JOINTS, TARGET)))}")

        errors = [abs(self.latest[name] - target) for name, target in zip(ARM_JOINTS, TARGET, strict=True)]
        moved = max(abs(self.latest[name] - self.initial[name]) for name in ARM_JOINTS) > 0.05
        reached = max(errors) < 0.08
        if reached or time.monotonic() - self.command_started > 20:
            result = {
                "timestamp": time.time(),
                "positions": self.latest,
                "target": dict(zip(ARM_JOINTS, TARGET, strict=True)),
                "max_abs_error": max(errors),
                "robot_moved": moved,
                "target_reached": reached,
            }
            (RESULT_DIR / "joint_state_after.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            self.get_logger().info(f"RESULT_STATE={json.dumps(result)}")
            self.done = True


def main() -> None:
    rclpy.init()
    node = FrankaJointCommandTest()
    try:
        while rclpy.ok() and not node.done:
            rclpy.spin_once(node, timeout_sec=0.2)
        if node.latest is None or node.initial is None:
            raise RuntimeError("没有收到有效的 Franka joint state")
        after = json.loads((RESULT_DIR / "joint_state_after.json").read_text(encoding="utf-8"))
        if not after["robot_moved"] or not after["target_reached"] or not math.isfinite(after["max_abs_error"]):
            raise RuntimeError(f"关节闭环验收失败：{after}")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
