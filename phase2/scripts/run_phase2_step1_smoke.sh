#!/usr/bin/env bash
set -eo pipefail

source /root/autodl-tmp/VLA-Intern-Sprint/phase2/scripts/isaac_env.sh

RESULT_DIR="$ISAAC_PROJECT/results/phase2_step1"
rm -f "$RESULT_DIR/isaac_ready.json" "$RESULT_DIR/isaac_exception.txt" "$RESULT_DIR/stop_isaac"

"$ISAAC_ENV/bin/python" "$ISAAC_PROJECT/phase2/scripts/isaac_franka_ros2_bridge.py" \
  > "$RESULT_DIR/isaac_runtime_profile.log" 2>&1 &
ISAAC_PID=$!

echo "timestamp,name,total_mib,used_mib,gpu_util_percent" > "$RESULT_DIR/gpu_timeseries.csv"
(
  while kill -0 "$ISAAC_PID" 2>/dev/null; do
    nvidia-smi \
      --query-gpu=timestamp,name,memory.total,memory.used,utilization.gpu \
      --format=csv,noheader,nounits >> "$RESULT_DIR/gpu_timeseries.csv"
    sleep 1
  done
) &
MONITOR_PID=$!

for _ in $(seq 1 90); do
  test -f "$RESULT_DIR/isaac_ready.json" && break
  kill -0 "$ISAAC_PID" 2>/dev/null || break
  sleep 1
done

NODE_EXIT=90
if test -f "$RESULT_DIR/isaac_ready.json"; then
  export ROS_DOMAIN_ID=42
  # Isaac 子进程已继承内置 Humble 库；外部 ROS 2 CLI 必须使用系统 Humble 库。
  unset LD_LIBRARY_PATH
  source /opt/ros/humble/setup.bash
  source /root/autodl-tmp/ros2_ws/install/setup.bash
  set +e
  timeout 45 ros2 run vla_manipulator_runtime franka_joint_command_test \
    > "$RESULT_DIR/joint_command_profile.log" 2>&1
  NODE_EXIT=$?
  set -e
fi

touch "$RESULT_DIR/stop_isaac"
wait "$ISAAC_PID" || true
wait "$MONITOR_PID" || true

python3 - "$RESULT_DIR/gpu_timeseries.csv" "$RESULT_DIR/gpu_peak.txt" <<'PY'
import csv
import sys

source, target = sys.argv[1:]
with open(source, newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
peak = max(float(row["used_mib"].strip()) for row in rows)
with open(target, "w", encoding="utf-8") as handle:
    handle.write(f"peak_gpu_vram_mib={peak:.0f}\n")
print(f"peak_gpu_vram_mib={peak:.0f}")
PY

echo "profile_node_exit=$NODE_EXIT"
exit "$NODE_EXIT"
