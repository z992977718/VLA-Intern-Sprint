#!/usr/bin/env python3
"""订阅两路 RGB 和 /joint_states，保存一个不含 policy 推理的 Observation Snapshot。"""

from __future__ import annotations

import json
import math
import os
import struct
import time
import zlib
from pathlib import Path

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, JointState


RESULT_DIR = Path(
    os.environ.get(
        "PHASE2_RESULT_DIR",
        "/root/autodl-tmp/VLA-Intern-Sprint/results/phase2_step2",
    )
)
CAMERAS = {
    "external": ("/phase2/external_camera/rgb", "camera_external.png"),
    "wrist": ("/phase2/wrist_camera/rgb", "camera_wrist.png"),
}
LANGUAGE = os.environ.get("PHASE2_LANGUAGE", "move the robot arm")


def stamp_to_sec(stamp) -> float:
    return float(stamp.sec) + float(stamp.nanosec) / 1_000_000_000.0


def image_to_rgb_bytes(msg: Image) -> bytes:
    channels = {
        "rgb8": 3,
        "bgr8": 3,
        "rgba8": 4,
        "bgra8": 4,
    }.get(msg.encoding.lower())
    if channels is None:
        raise ValueError(f"不支持的图像编码: {msg.encoding}")

    source = memoryview(msg.data)
    output = bytearray(msg.width * msg.height * 3)
    encoding = msg.encoding.lower()
    for y in range(msg.height):
        row = source[y * msg.step : y * msg.step + msg.width * channels]
        for x in range(msg.width):
            source_offset = x * channels
            target_offset = (y * msg.width + x) * 3
            if encoding.startswith("rgb"):
                red, green, blue = row[source_offset : source_offset + 3]
            else:
                blue, green, red = row[source_offset : source_offset + 3]
            output[target_offset : target_offset + 3] = bytes((red, green, blue))
    return bytes(output)


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))


def save_rgb_png(path: Path, width: int, height: int, rgb: bytes) -> None:
    stride = width * 3
    scanlines = b"".join(b"\x00" + rgb[y * stride : (y + 1) * stride] for y in range(height))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(scanlines, level=6))
        + png_chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def values_by_name(names: list[str], values: list[float]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for index, name in enumerate(names):
        value = float(values[index]) if index < len(values) else None
        result[name] = value if value is None or math.isfinite(value) else None
    return result


class ObservationAdapter(Node):
    def __init__(self) -> None:
        super().__init__("observation_adapter_node")
        RESULT_DIR.mkdir(parents=True, exist_ok=True)
        self.images: dict[str, dict] = {}
        self.joint_state: dict | None = None
        self.done = False
        self.started = time.monotonic()
        self.create_subscription(JointState, "/joint_states", self.on_joint_state, 10)
        for label, (topic, _) in CAMERAS.items():
            self.create_subscription(Image, topic, lambda msg, label=label: self.on_image(label, msg), 10)

    def on_joint_state(self, msg: JointState) -> None:
        names = list(msg.name)
        self.joint_state = {
            "topic": "/joint_states",
            "header_timestamp_sec": stamp_to_sec(msg.header.stamp),
            "received_wall_time_sec": time.time(),
            "raw_order": names,
            "raw_dimensions": {
                "name": len(msg.name),
                "position": len(msg.position),
                "velocity": len(msg.velocity),
                "effort": len(msg.effort),
            },
            "position_by_name": values_by_name(names, list(msg.position)),
            "velocity_by_name": values_by_name(names, list(msg.velocity)),
            "effort_by_name": values_by_name(names, list(msg.effort)),
        }
        self.try_save()

    def on_image(self, label: str, msg: Image) -> None:
        if label in self.images:
            return
        rgb = image_to_rgb_bytes(msg)
        _, filename = CAMERAS[label]
        path = RESULT_DIR / filename
        save_rgb_png(path, msg.width, msg.height, rgb)
        pixel_count = len(rgb)
        pixel_mean = sum(rgb) / pixel_count
        pixel_variance = sum((value - pixel_mean) ** 2 for value in rgb) / pixel_count
        image_pixel_count = msg.width * msg.height
        dark_pixel_count = sum(
            max(rgb[offset : offset + 3]) <= 5 for offset in range(0, len(rgb), 3)
        )
        self.images[label] = {
            "topic": CAMERAS[label][0],
            "path": str(path),
            "shape": [int(msg.height), int(msg.width), 3],
            "dtype": "uint8",
            "source_encoding": msg.encoding,
            "saved_encoding": "rgb8",
            "width": int(msg.width),
            "height": int(msg.height),
            "step": int(msg.step),
            "frame_id": msg.header.frame_id,
            "header_timestamp_sec": stamp_to_sec(msg.header.stamp),
            "received_wall_time_sec": time.time(),
            "data_size_bytes": len(msg.data),
            "pixel_min": min(rgb),
            "pixel_max": max(rgb),
            "pixel_mean": pixel_mean,
            "pixel_std": math.sqrt(pixel_variance),
            "dark_pixel_ratio_at_most_5": dark_pixel_count / image_pixel_count,
        }
        self.get_logger().info(f"收到 {label} RGB: {msg.width}x{msg.height} {msg.encoding}")
        self.try_save()

    def try_save(self) -> None:
        if self.done or self.joint_state is None or set(self.images) != set(CAMERAS):
            return

        eef_pose_path = RESULT_DIR / "eef_pose.json"
        if not eef_pose_path.is_file():
            return
        eef_pose = json.loads(eef_pose_path.read_text(encoding="utf-8"))

        image_deltas = {
            name: abs(meta["header_timestamp_sec"] - self.joint_state["header_timestamp_sec"])
            for name, meta in self.images.items()
        }
        timing = {
            "camera_header_timestamp_sec": {
                name: meta["header_timestamp_sec"] for name, meta in self.images.items()
            },
            "joint_state_header_timestamp_sec": self.joint_state["header_timestamp_sec"],
            "observation_creation_wall_time_sec": time.time(),
            "image_to_joint_state_abs_delta_sec": image_deltas,
            "max_image_to_joint_state_abs_delta_sec": max(image_deltas.values()),
            "synchronization": "latest-message approximate pairing; no message_filters",
        }
        camera_metadata = {
            "count": len(self.images),
            "cameras": self.images,
        }
        observation = {
            "timestamp": timing["observation_creation_wall_time_sec"],
            "images": self.images,
            "robot_state": {
                "source": "/joint_states",
                "kinematics_source": eef_pose["source"],
                "eef_pose": eef_pose,
                "semantics": "named Isaac Franka joints plus panda_hand world transform; 8D conversion is delegated to the policy input adapter",
                "joint_positions": self.joint_state["position_by_name"],
                "joint_velocities": self.joint_state["velocity_by_name"],
                "joint_efforts": self.joint_state["effort_by_name"],
            },
            "language": LANGUAGE,
            "policy_inference_executed": False,
            "joint_command_publisher_created": False,
            "vla_action_sent": False,
        }
        (RESULT_DIR / "camera_metadata.json").write_text(
            json.dumps(camera_metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (RESULT_DIR / "joint_state.json").write_text(
            json.dumps(self.joint_state, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (RESULT_DIR / "timing.json").write_text(
            json.dumps(timing, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (RESULT_DIR / "observation_snapshot.json").write_text(
            json.dumps(observation, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self.done = True
        self.get_logger().info(f"OBSERVATION_SNAPSHOT={RESULT_DIR / 'observation_snapshot.json'}")


def main() -> None:
    rclpy.init()
    node = ObservationAdapter()
    try:
        while rclpy.ok() and not node.done:
            rclpy.spin_once(node, timeout_sec=0.2)
            if time.monotonic() - node.started > 60:
                raise TimeoutError("60 秒内未收到两路 RGB 和 /joint_states")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
