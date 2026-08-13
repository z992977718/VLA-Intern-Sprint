#!/usr/bin/env bash
set -eo pipefail

source /root/autodl-tmp/VLA-Intern-Sprint/phase2/scripts/isaac_env.sh

RESULT_DIR="$ISAAC_PROJECT/results/phase2_step2"
mkdir -p "$RESULT_DIR"
rm -f \
  "$RESULT_DIR/isaac_ready.json" \
  "$RESULT_DIR/isaac_exception.txt" \
  "$RESULT_DIR/stop_isaac" \
  "$RESULT_DIR/camera_metadata.json" \
  "$RESULT_DIR/joint_state.json" \
  "$RESULT_DIR/observation_snapshot.json" \
  "$RESULT_DIR/timing.json" \
  "$RESULT_DIR/camera_external.png" \
  "$RESULT_DIR/camera_wrist.png"

"$ISAAC_ENV/bin/python" "$ISAAC_PROJECT/phase2/scripts/isaac_franka_camera_ros2.py" \
  > "$RESULT_DIR/isaac_runtime.log" 2>&1 &
ISAAC_PID=$!

echo "timestamp,name,total_mib,used_mib,gpu_util_percent" > "$RESULT_DIR/gpu_timeseries.csv"
(
  while kill -0 "$ISAAC_PID" 2>/dev/null; do
    nvidia-smi --query-gpu=timestamp,name,memory.total,memory.used,utilization.gpu \
      --format=csv,noheader,nounits >> "$RESULT_DIR/gpu_timeseries.csv"
    sleep 1
  done
) &
MONITOR_PID=$!

for _ in $(seq 1 120); do
  test -f "$RESULT_DIR/isaac_ready.json" && break
  kill -0 "$ISAAC_PID" 2>/dev/null || break
  sleep 1
done

NODE_EXIT=90
if test -f "$RESULT_DIR/isaac_ready.json"; then
  export ROS_DOMAIN_ID=42
  unset LD_LIBRARY_PATH
  source /opt/ros/humble/setup.bash
  source /root/autodl-tmp/ros2_ws/install/setup.bash

  ros2 topic list > "$RESULT_DIR/ros2_topics.txt"
  {
    ros2 topic info --verbose /phase2/external_camera/rgb
    ros2 topic info --verbose /phase2/wrist_camera/rgb
    ros2 topic info --verbose /joint_states
  } > "$RESULT_DIR/ros2_topic_info.txt" 2>&1

  set +e
  timeout 75 ros2 run vla_manipulator_runtime observation_adapter_node \
    > "$RESULT_DIR/observation_adapter.log" 2>&1
  NODE_EXIT=$?
  set -e
fi

touch "$RESULT_DIR/stop_isaac"
wait "$ISAAC_PID" || true
wait "$MONITOR_PID" || true

python3 - "$RESULT_DIR" "$NODE_EXIT" <<'PY'
import csv
import json
import sys
from pathlib import Path

result_dir = Path(sys.argv[1])
node_exit = int(sys.argv[2])
rows = list(csv.DictReader((result_dir / "gpu_timeseries.csv").open(encoding="utf-8")))
peak = max((float(row["used_mib"].strip()) for row in rows), default=0.0)
(result_dir / "gpu_peak.txt").write_text(f"peak_gpu_vram_mib={peak:.0f}\n", encoding="utf-8")

required = [
    "camera_metadata.json", "joint_state.json", "observation_snapshot.json", "timing.json",
    "ros2_topics.txt", "ros2_topic_info.txt", "camera_external.png", "camera_wrist.png",
]
missing = [name for name in required if not (result_dir / name).is_file()]
invalid_frames = []
metadata_path = result_dir / "camera_metadata.json"
if metadata_path.is_file():
    camera_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    for label, frame in camera_metadata.get("cameras", {}).items():
        if (
            frame.get("pixel_std", 0.0) <= 1.0
            or frame.get("pixel_max") == frame.get("pixel_min")
            or frame.get("dark_pixel_ratio_at_most_5", 1.0) >= 0.5
        ):
            invalid_frames.append(label)
summary = {
    "node_exit": node_exit,
    "missing": missing,
    "invalid_frames": invalid_frames,
    "peak_gpu_vram_mib": peak,
}
(result_dir / "run_status.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary))
if node_exit != 0 or missing or invalid_frames:
    raise SystemExit(1)
PY
