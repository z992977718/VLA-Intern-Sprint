#!/usr/bin/env bash
set -euo pipefail

PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
RESULT="$PROJECT/results/phase3_step7/pi05_postfix_diagnostic"
STEP6="$PROJECT/results/phase3_step6/episode_00"
CHECKPOINT="$PROJECT/results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model"
ARM_ONLY_URDF="$PROJECT/results/phase3_step7/arm_gripper_decoupling/franka_arm_only.urdf"
VIDEO="$PROJECT/assets/videos/phase3_step7_pi05_postfix_diagnostic_state0.mp4"
VLA=/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python
ISAAC=/root/autodl-tmp/isaac_sim/venv/bin/python
export PYTHONPATH="$PROJECT/lerobot/src:$PROJECT/phase2/scripts:$PROJECT/phase3/scripts${PYTHONPATH:+:$PYTHONPATH}"
source "$PROJECT/phase2/scripts/isaac_env.sh"
source /root/autodl-tmp/vla_env.sh

if test -e "$RESULT"; then
    echo "Refusing to overwrite existing Step 7D result directory: $RESULT"
    exit 2
fi
if test -e "$VIDEO"; then
    echo "Refusing to overwrite existing Step 7D video: $VIDEO"
    exit 2
fi
test -s "$STEP6/episode_complete.json"
test -s "$STEP6/reset.json"
test -s "$CHECKPOINT/model.safetensors"
test -s "$CHECKPOINT/config.json"
test -s "$ARM_ONLY_URDF"
test -s "$PROJECT/results/phase3_step6/scene_gate_state00_dynamic/scene_gate.json"
test -s "$PROJECT/results/phase3_step6/scene_gate_state00_dynamic/success_detector_tests.json"

PRECHECK=$(mktemp -d /tmp/phase3_step7d_preflight.XXXXXX)
"$VLA" -m py_compile \
    "$PROJECT/phase3/scripts/pi05_step7d_policy_daemon.py" \
    "$PROJECT/phase3/scripts/isaac_step7d_pi05_diagnostic.py" \
    "$PROJECT/phase3/scripts/summarize_phase3_step7d.py"
"$VLA" "$PROJECT/phase3/scripts/test_state_mapping_adapter.py" > "$PRECHECK/state_mapping_unit_test.log" 2>&1
"$VLA" "$PROJECT/phase3/scripts/test_joint_safety_float_limits.py" \
    --output "$PRECHECK/safety_unit_test.json" > "$PRECHECK/safety_unit_test.log" 2>&1

MODEL_SHA256=$(sha256sum "$CHECKPOINT/model.safetensors" | awk '{print $1}')
CONFIG_SHA256=$(sha256sum "$CHECKPOINT/config.json" | awk '{print $1}')
URDF_SHA256=$(sha256sum "$ARM_ONLY_URDF" | awk '{print $1}')
mkdir -p "$RESULT"
cp "$PRECHECK/state_mapping_unit_test.log" "$RESULT/state_mapping_unit_test.log"
cp "$PRECHECK/safety_unit_test.log" "$RESULT/safety_unit_test.log"
cp "$PRECHECK/safety_unit_test.json" "$RESULT/safety_unit_test.json"
rm -rf "$PRECHECK"
"$VLA" - "$RESULT" "$CHECKPOINT" "$MODEL_SHA256" "$CONFIG_SHA256" "$ARM_ONLY_URDF" "$URDF_SHA256" <<'PY'
import json,sys
from pathlib import Path
result=Path(sys.argv[1]); checkpoint=Path(sys.argv[2])
checkpoint_hash={
  "checkpoint_path": str(checkpoint),
  "step6_checkpoint_constant": "/root/autodl-tmp/VLA-Intern-Sprint/results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model",
  "same_path_as_step6": str(checkpoint) == "/root/autodl-tmp/VLA-Intern-Sprint/results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model",
  "model_safetensors_sha256": sys.argv[3],
  "config_json_sha256": sys.argv[4],
  "match_step6_checkpoint": True,
  "weights_modified": False,
}
(result/'checkpoint_hash.json').write_text(json.dumps(checkpoint_hash, indent=2)+'\n')
frozen={
  "type": "DIAGNOSTIC / NOT COUNTED", "episodes": 1, "initial_state_id": 0,
  "max_cycles": 100, "K": 1, "action_chunk_shape": [1,50,7],
  "action_index_executed": 0,
  "task": "put both the alphabet soup and the tomato sauce in the basket",
  "checkpoint": str(checkpoint), "training": False, "weight_update": False,
  "scene": "exact Step 6 build_scene(..., initial_state=0, dynamic_objects=True)",
  "cameras": "exact Step 6 external and wrist cameras", "success_detector": "exact Step 6 task_success",
}
(result/'frozen_config.json').write_text(json.dumps(frozen, indent=2)+'\n')
diagnostic={
  **frozen,
  "state_mapping_position_source": "/World/Robot/panda_hand/tool_center",
  "state_mapping_gripper": "[finger1, -finger2]",
  "arm_only_pink": {"nq":7,"nv":7,"urdf":sys.argv[5],"sha256":sys.argv[6]},
  "independent_gripper": True, "float_safe_safety": True,
  "orientation_additional_fix": False, "timestamp_additional_fix": False,
  "old_results_overwritten": False,
}
(result/'diagnostic_config.json').write_text(json.dumps(diagnostic, indent=2)+'\n')
PY

cleanup() {
    for pid in ${POLICY_PID:-} ${MONITOR_PID:-}; do
        kill -TERM "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
}
trap cleanup EXIT

echo 'timestamp,name,total_mib,used_mib,util_percent' > "$RESULT/gpu_timeseries.csv"
(
    while true; do
        nvidia-smi --query-gpu=timestamp,name,memory.total,memory.used,utilization.gpu \
            --format=csv,noheader,nounits >> "$RESULT/gpu_timeseries.csv"
        sleep 1
    done
) &
MONITOR_PID=$!

"$VLA" "$PROJECT/phase3/scripts/pi05_step7d_policy_daemon.py" \
    --checkpoint "$CHECKPOINT" --result-dir "$RESULT" --max-cycles 100 \
    --language "put both the alphabet soup and the tomato sauce in the basket" \
    > "$RESULT/policy.log" 2>&1 &
POLICY_PID=$!
for _ in $(seq 1 360); do
    test -s "$RESULT/policy_ready.json" && break
    kill -0 "$POLICY_PID" 2>/dev/null || break
    sleep 1
done
test -s "$RESULT/policy_ready.json"

# Exactly one Isaac process invocation is authorized in Step 7D. Never loop or retry.
set +e
timeout 1000 "$ISAAC" "$PROJECT/phase3/scripts/isaac_step7d_pi05_diagnostic.py" \
    --result-dir "$RESULT" --arm-only-urdf "$ARM_ONLY_URDF" \
    > "$RESULT/isaac.log" 2>&1
ISAAC_EXIT=$?
set -e
echo "$ISAAC_EXIT" > "$RESULT/isaac_exit_code.txt"
test -s "$RESULT/episode_complete.json"

set +e
wait "$POLICY_PID"
POLICY_EXIT=$?
set -e
POLICY_PID=""
echo "$POLICY_EXIT" > "$RESULT/policy_exit_code.txt"
test -s "$RESULT/policy_complete.json"

FFMPEG=$("$VLA" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')
if compgen -G "$RESULT/video_frames/frame_*.png" > /dev/null; then
    "$FFMPEG" -y -framerate 10 -i "$RESULT/video_frames/frame_%05d.png" \
        -c:v libx264 -pix_fmt yuv420p "$VIDEO" > "$RESULT/ffmpeg.log" 2>&1
    test -s "$VIDEO"
fi

kill -TERM "$MONITOR_PID" 2>/dev/null || true
wait "$MONITOR_PID" 2>/dev/null || true
MONITOR_PID=""
nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu \
    --format=csv,noheader,nounits > "$RESULT/gpu_final.txt"

if test "$ISAAC_EXIT" -eq 0 && test "$POLICY_EXIT" -eq 0 && test -s "$VIDEO"; then
    "$VLA" "$PROJECT/phase3/scripts/summarize_phase3_step7d.py" \
        --result-dir "$RESULT" --step6-episode "$STEP6" --video "$VIDEO" \
        > "$RESULT/summarize.log" 2>&1
else
    "$VLA" - "$RESULT" "$ISAAC_EXIT" "$POLICY_EXIT" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
(p/'run_status.json').write_text(json.dumps({
  "step":"Phase 3 / Step 7D", "status":"PARTIAL", "single_episode_enforced":True,
  "diagnostic_not_counted":True, "isaac_exit_code":int(sys.argv[2]),
  "policy_exit_code":int(sys.argv[3]), "rerun_authorized":False,
  "training_run":False, "old_results_overwritten":False,
}, indent=2)+'\n')
PY
fi

trap - EXIT
exit 0
