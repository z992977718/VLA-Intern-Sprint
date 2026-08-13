#!/usr/bin/env bash
set -euo pipefail
PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
RESULT="$PROJECT/results/phase2_step4"
CHECKPOINT="$PROJECT/results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model"
VLA=/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python
ISAAC=/root/autodl-tmp/isaac_sim/venv/bin/python
mkdir -p "$RESULT" "$PROJECT/assets/images" "$PROJECT/assets/videos"

# Gate 1 must already be proven.
"$VLA" - "$RESULT/synthetic_action_test.json" <<'PY'
import json,sys
assert json.load(open(sys.argv[1]))["pass"] is True
PY

# Fresh real Isaac + ROS2 two-camera Observation, identical to Step 3 acquisition.
source "$PROJECT/phase2/scripts/isaac_env.sh"
export PHASE2_RESULT_DIR="$RESULT" PHASE2_ISAAC_TIMEOUT_SEC=300 PHASE2_LANGUAGE="move the robot arm"
rm -f "$RESULT/stop_isaac" "$RESULT/isaac_ready.json" "$RESULT/eef_pose.json" "$RESULT/joint_state.json" \
      "$RESULT/camera_external.png" "$RESULT/camera_wrist.png" "$RESULT/vla_action_raw.npy" \
      "$RESULT/vla_action_processed.json" "$RESULT/vla_action_bounded.json" "$RESULT/execution_exception.txt"
"$ISAAC" "$PROJECT/phase2/scripts/isaac_franka_camera_ros2.py" >"$RESULT/observation_isaac.log" 2>&1 & ISAAC_PID=$!
cleanup(){ touch "$RESULT/stop_isaac"; kill -TERM "$ISAAC_PID" 2>/dev/null||true; wait "$ISAAC_PID" 2>/dev/null||true; }
trap cleanup EXIT
for _ in $(seq 1 120); do test -s "$RESULT/isaac_ready.json" && break; kill -0 "$ISAAC_PID" 2>/dev/null||break; sleep 1; done
test -s "$RESULT/isaac_ready.json"
export ROS_DOMAIN_ID=42; unset LD_LIBRARY_PATH; set +u; source /opt/ros/humble/setup.bash; source /root/autodl-tmp/ros2_ws/install/setup.bash; set -u
timeout 75 python3 "$PROJECT/phase2/ros2_ws/src/vla_manipulator_runtime/vla_manipulator_runtime/observation_adapter_node.py" >"$RESULT/observation_adapter.log" 2>&1
cleanup; trap - EXIT; ISAAC_PID=""
for f in camera_external.png camera_wrist.png joint_state.json eef_pose.json observation_snapshot.json; do test -s "$RESULT/$f"; done

# Exactly one inference call; prepares but does not publish action.
(cd "$PROJECT"; export PYTHONPATH="$PROJECT/lerobot/src:$PROJECT/phase2/scripts${PYTHONPATH:+:$PYTHONPATH}"; source /root/autodl-tmp/vla_env.sh; \
 "$VLA" "$PROJECT/phase2/scripts/run_pi05_step4_once.py" --checkpoint "$CHECKPOINT" --result-dir "$RESULT" --language "$PHASE2_LANGUAGE") \
 >"$RESULT/policy_once.log" 2>&1
test -s "$RESULT/vla_action_bounded.json"

# Execute exactly action_chunk[0] in a fresh deterministic reset of the captured state.
export PHASE2_STEP4_RESULT="$RESULT" PHASE2_STEP4_ASSET="$PROJECT/assets"
"$ISAAC" "$PROJECT/phase2/scripts/isaac_step4_execute_one.py" >"$RESULT/execution_run.log" 2>&1
for f in before_state.json after_state.json joint_target.json execution_error.json controller_metrics.json; do test -s "$RESULT/$f"; done

"$VLA" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())' > "$RESULT/ffmpeg_path.txt"
"$(cat "$RESULT/ffmpeg_path.txt")" -y -framerate 10 -i "$RESULT/video_frames/frame_%04d.png" -c:v libx264 -pix_fmt yuv420p \
  "$PROJECT/assets/videos/phase2_step4_action_execution.mp4" >"$RESULT/ffmpeg.log" 2>&1
test -s "$PROJECT/assets/images/phase2_step4_before.png"
test -s "$PROJECT/assets/images/phase2_step4_after.png"
test -s "$PROJECT/assets/videos/phase2_step4_action_execution.mp4"
