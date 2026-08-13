#!/usr/bin/env bash
set -euo pipefail

PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
RESULT_DIR="$PROJECT/results/phase2_step3"
CHECKPOINT="$PROJECT/results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model"
ISAAC_PYTHON=/root/autodl-tmp/isaac_sim/venv/bin/python
VLA_PYTHON=/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python

source "$PROJECT/phase2/scripts/isaac_env.sh"
export PHASE2_RESULT_DIR="$RESULT_DIR"
export PHASE2_ISAAC_TIMEOUT_SEC=600
export PHASE2_LANGUAGE="move the robot arm"

mkdir -p "$RESULT_DIR"
for name in \
  isaac_ready.json isaac_exception.txt stop_isaac eef_pose.json direct_camera_stats.json \
  camera_metadata.json joint_state.json observation_snapshot.json timing.json \
  camera_external.png camera_wrist.png policy_input_external.png policy_input_wrist.png \
  checkpoint_config.json input_schema.json robot_state_sample.json action_chunk.npy \
  action_chunks_3_calls.npy action_chunk_summary.json inference_latency.json gpu_memory.txt \
  environment.txt policy_run_status.json run_status.json gpu_timeseries.csv gpu_peak.txt \
  ros2_topics.txt ros2_topic_info.txt isaac_runtime.log observation_adapter.log policy_inference.log; do
  rm -f "$RESULT_DIR/$name"
done

cleanup() {
  touch "$RESULT_DIR/stop_isaac"
  if test -n "${ISAAC_PID:-}" && kill -0 "$ISAAC_PID" 2>/dev/null; then
    kill -TERM "$ISAAC_PID" 2>/dev/null || true
    wait "$ISAAC_PID" || true
  fi
  if test -n "${MONITOR_PID:-}" && kill -0 "$MONITOR_PID" 2>/dev/null; then
    kill -TERM "$MONITOR_PID" 2>/dev/null || true
    wait "$MONITOR_PID" || true
  fi
}
trap cleanup EXIT

"$ISAAC_PYTHON" "$PROJECT/phase2/scripts/isaac_franka_camera_ros2.py" \
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

for _ in $(seq 1 180); do
  test -f "$RESULT_DIR/isaac_ready.json" && break
  kill -0 "$ISAAC_PID" 2>/dev/null || break
  sleep 1
done
test -f "$RESULT_DIR/isaac_ready.json"
test -f "$RESULT_DIR/eef_pose.json"

export ROS_DOMAIN_ID=42
unset LD_LIBRARY_PATH
set +u
source /opt/ros/humble/setup.bash
source /root/autodl-tmp/ros2_ws/install/setup.bash
set -u
ros2 topic list > "$RESULT_DIR/ros2_topics.txt"
{
  ros2 topic info --verbose /phase2/external_camera/rgb
  ros2 topic info --verbose /phase2/wrist_camera/rgb
  ros2 topic info --verbose /joint_states
  ros2 topic info --verbose /joint_command || true
} > "$RESULT_DIR/ros2_topic_info.txt" 2>&1

timeout 75 python3 \
  "$PROJECT/phase2/ros2_ws/src/vla_manipulator_runtime/vla_manipulator_runtime/observation_adapter_node.py" \
  > "$RESULT_DIR/observation_adapter.log" 2>&1

touch "$RESULT_DIR/stop_isaac"
wait "$ISAAC_PID" || true
kill -TERM "$MONITOR_PID" 2>/dev/null || true
wait "$MONITOR_PID" || true
ISAAC_PID=""
MONITOR_PID=""

(
  cd "$PROJECT"
  export PYTHONPATH="$PROJECT/lerobot/src:$PROJECT/phase2/scripts${PYTHONPATH:+:$PYTHONPATH}"
  source /root/autodl-tmp/vla_env.sh
  "$VLA_PYTHON" "$PROJECT/phase2/scripts/run_pi05_step3_inference.py" \
    --checkpoint "$CHECKPOINT" \
    --result-dir "$RESULT_DIR" \
    --language "$PHASE2_LANGUAGE"
) > "$RESULT_DIR/policy_inference.log" 2>&1
trap - EXIT

"$VLA_PYTHON" - "$RESULT_DIR" <<'PY'
import csv
import json
import sys
from pathlib import Path

result_dir = Path(sys.argv[1])
rows = list(csv.DictReader((result_dir / "gpu_timeseries.csv").open(encoding="utf-8")))
peak = max((float(row["used_mib"].strip()) for row in rows), default=0.0)
(result_dir / "gpu_peak.txt").write_text(f"peak_nvidia_smi_used_mib={peak:.0f}\n", encoding="utf-8")
required = [
    "environment.txt", "input_schema.json", "robot_state_sample.json",
    "observation_snapshot.json", "action_chunk.npy", "action_chunk_summary.json",
    "inference_latency.json", "gpu_memory.txt", "policy_input_external.png",
    "policy_input_wrist.png", "policy_run_status.json",
]
missing = [name for name in required if not (result_dir / name).is_file()]
policy = json.loads((result_dir / "policy_run_status.json").read_text(encoding="utf-8"))
status = {
    "isaac_sim": "PASS" if (result_dir / "isaac_ready.json").is_file() else "FAIL",
    "franka": "PASS" if (result_dir / "eef_pose.json").is_file() else "FAIL",
    "two_cameras": "PASS" if all((result_dir / name).is_file() for name in ["camera_external.png", "camera_wrist.png"]) else "FAIL",
    "joint_states": "PASS" if (result_dir / "joint_state.json").is_file() else "FAIL",
    "policy": policy,
    "peak_nvidia_smi_used_mib": peak,
    "missing_artifacts": missing,
    "action_sent": False,
    "step3": "PASS" if not missing and policy["inference"] == "PASS" else "FAIL",
}
(result_dir / "run_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
print(json.dumps(status))
if status["step3"] != "PASS":
    raise SystemExit(1)
PY

nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader \
  > "$RESULT_DIR/gpu_processes_after.txt" || true
