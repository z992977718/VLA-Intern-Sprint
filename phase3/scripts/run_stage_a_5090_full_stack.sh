#!/usr/bin/env bash
# RTX 5090 Stage A: isolated full-stack smoke test. No training or task rollout.
set -euo pipefail

PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
RESULT="$PROJECT/results/migration_smoke_5090_isaac_attempt03"
CHECKPOINT="$PROJECT/results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model"
VLA=/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python
ISAAC=/root/autodl-tmp/isaac_sim/venv/bin/python

test ! -e "$RESULT"
mkdir -p "$RESULT" "$RESULT/assets/images" "$RESULT/assets/videos"
source "$PROJECT/phase2/scripts/isaac_env.sh"
export PYTHONPATH="$PROJECT/lerobot/src:$PROJECT/phase2/scripts:$PROJECT/phase3/scripts${PYTHONPATH:+:$PYTHONPATH}"

nvidia-smi > "$RESULT/environment.txt"
{
  echo "hostname=$(hostname)"
  echo "isaac_python=$ISAAC"
  "$ISAAC" -c 'from isaacsim import SimulationApp; print("isaac_import=OK")'
} >> "$RESULT/environment.txt" 2>&1
VK_ICD_FILENAMES=/etc/vulkan/icd.d/my_nvidia_icd.json vulkaninfo --summary > "$RESULT/vulkan.txt" 2>&1

# A3: one isolated, non-policy controller calibration suite, including +X.
export PHASE2_STEP4_RESULT="$RESULT/synthetic"
mkdir -p "$PHASE2_STEP4_RESULT"
"$ISAAC" "$PROJECT/phase2/scripts/isaac_step4_synthetic.py" > "$RESULT/synthetic.log" 2>&1
test "$("$VLA" -c "import json; print(json.load(open('$RESULT/synthetic/synthetic_action_test.json'))['pass'])")" = True

# A1/A2: Isaac headless rendering and actual ROS2 bridge/adapter observation.
export PHASE2_RESULT_DIR="$RESULT/observation"
export PHASE2_ISAAC_TIMEOUT_SEC=300
export PHASE2_LANGUAGE="put both the alphabet soup and the tomato sauce in the basket"
mkdir -p "$PHASE2_RESULT_DIR"
"$ISAAC" "$PROJECT/phase2/scripts/isaac_franka_camera_ros2.py" > "$RESULT/observation/isaac.log" 2>&1 &
ISAAC_PID=$!
cleanup() {
  touch "$PHASE2_RESULT_DIR/stop_isaac"
  kill -TERM "${ISAAC_PID:-}" 2>/dev/null || true
  wait "${ISAAC_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT
while true; do
  test -s "$PHASE2_RESULT_DIR/isaac_ready.json" && break
  kill -0 "$ISAAC_PID" 2>/dev/null || {
    echo "Isaac exited before isaac_ready.json" >&2
    exit 1
  }
  sleep 2
done
test -s "$PHASE2_RESULT_DIR/isaac_ready.json"
export ROS_DOMAIN_ID=42
unset LD_LIBRARY_PATH
set +u
source /opt/ros/humble/setup.bash
source /root/autodl-tmp/ros2_ws/install/setup.bash
set -u
ros2 topic list > "$RESULT/ros_topics.txt"
{
  ros2 topic info --verbose /joint_states
  ros2 topic info --verbose /phase2/external_camera/rgb
  ros2 topic info --verbose /phase2/wrist_camera/rgb
} > "$RESULT/ros_topic_info.txt" 2>&1
timeout 75 python3 "$PROJECT/phase2/ros2_ws/src/vla_manipulator_runtime/vla_manipulator_runtime/observation_adapter_node.py" \
  > "$RESULT/observation/adapter.log" 2>&1
touch "$PHASE2_RESULT_DIR/stop_isaac"
wait "$ISAAC_PID"
ISAAC_PID=""
trap - EXIT
for file in camera_external.png camera_wrist.png joint_state.json eef_pose.json observation_snapshot.json timing.json; do
  test -s "$PHASE2_RESULT_DIR/$file"
done

# A4 policy inference once, followed by exactly action_chunk[0] in a fresh reset.
( cd "$PROJECT"; source /root/autodl-tmp/vla_env.sh; export PYTHONPATH="$PROJECT/lerobot/src:$PROJECT/phase2/scripts:$PROJECT/phase3/scripts"; \
  "$VLA" "$PROJECT/phase2/scripts/run_pi05_step4_once.py" --checkpoint "$CHECKPOINT" \
  --result-dir "$PHASE2_RESULT_DIR" --language "$PHASE2_LANGUAGE" ) > "$RESULT/policy.log" 2>&1
test -s "$PHASE2_RESULT_DIR/vla_action_bounded.json"
export PHASE2_STEP4_RESULT="$PHASE2_RESULT_DIR" PHASE2_STEP4_ASSET="$RESULT/assets"
"$ISAAC" "$PROJECT/phase2/scripts/isaac_step4_execute_one.py" > "$RESULT/execution.log" 2>&1
for file in execution_error.json controller_metrics.json before_state.json after_state.json; do
  test -s "$PHASE2_RESULT_DIR/$file"
done

nvidia-smi > "$RESULT/gpu_memory.txt"
"$VLA" - "$RESULT" <<'PY'
import json, sys
from pathlib import Path

root = Path(sys.argv[1]); obs = root / 'observation'
stats = json.loads((obs / 'direct_camera_stats.json').read_text())
timing = json.loads((obs / 'timing.json').read_text())
synthetic = json.loads((root / 'synthetic' / 'synthetic_action_test.json').read_text())
execution = json.loads((obs / 'execution_error.json').read_text())
action = json.loads((obs / 'vla_action_processed.json').read_text())
status = {
  'stage': 'A', 'pass': bool(synthetic['pass'] and execution['robot_moved']),
  'isaac_graphics': {'renderer': 'RaytracedLighting', 'camera_stats': stats},
  'ros2': {'joint_states': True, 'two_camera_topics': True,
           'max_image_state_skew_sec': timing['max_image_to_joint_state_abs_delta_sec']},
  'pink_synthetic': synthetic,
  'one_vla_action': {'action_chunk_shape': action['chunk_shape'], 'finite': True,
                     'robot_moved': execution['robot_moved'], 'target_position_error_m': execution['target_position_error_m']},
  'protocol': 'No training. One Pi0.5 predict_action_chunk and only action_chunk[0] executed. No task rollout.'
}
(root / 'run_status.json').write_text(json.dumps(status, indent=2)+'\n')
(root / 'summary.md').write_text('# RTX 5090 Isaac Full-Stack Migration Smoke Test\n\n'+json.dumps(status, indent=2)+'\n')
if not status['pass']: raise SystemExit(2)
PY
