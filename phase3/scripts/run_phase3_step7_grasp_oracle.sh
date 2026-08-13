#!/usr/bin/env bash
set -euo pipefail

PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
RESULT="$PROJECT/results/phase3_step7/grasp_oracle"
ISAAC=/root/autodl-tmp/isaac_sim/venv/bin/python
VLA=/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python

cd "$PROJECT"
source phase2/scripts/isaac_env.sh
export PYTHONPATH="$PROJECT/phase2/scripts:$PROJECT/phase3/scripts${PYTHONPATH:+:$PYTHONPATH}"
test ! -e "$RESULT" || { echo "Refusing to overwrite $RESULT" >&2; exit 2; }
mkdir -p "$RESULT"

{
  echo "Isaac: $($ISAAC -c 'import isaacsim; print(isaacsim.__file__)')"
  echo "Scene: Phase 3 Step 6 build_scene(initial_state_id=0, dynamic_objects=true)"
  echo "Controller: PinkIKController + OSQP + Franka"
  echo "Policy: NOT USED"
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
} > "$RESULT/environment.txt"

cat > "$RESULT/oracle_config.json" <<'JSON'
{
  "initial_state_id": 0,
  "objects": ["alphabet_soup", "tomato_sauce"],
  "formal_trials_per_object": 3,
  "hard_reset_per_trial": true,
  "policy": "not used",
  "trajectory": "top-down: approach, descent, close, settle, lift, hold",
  "lift_success_threshold_m": 0.06,
  "physics": "reused unchanged from Phase 3 Step 6"
}
JSON

# The diagnostic is deliberately separate and not counted. Inspect its result
# before invoking this formal six-trial runner.
cat > "$RESULT/success_metric.json" <<'JSON'
{
  "success_requirements": [
    "close command target 0 is issued and maintained; actual nonzero width is allowed when object contact blocks further closure",
    "object maximum vertical displacement is >= 0.060 m",
    "object final vertical displacement is >= 0.045 m after hold"
  ],
  "not_sufficient": ["gripper command alone", "contact alone", "EEF movement alone"],
  "object_motion_source": "live dynamic object root world pose"
}
JSON

for object in alphabet tomato; do
  for index in 0 1 2; do
    folder="$RESULT/${object}_$(printf '%02d' "$index")"
    set +e
    timeout 720 "$ISAAC" phase3/scripts/isaac_step7_grasp_oracle.py --object "$object" --trial-index "$index" --output-dir "$folder" >"$folder.launch.log" 2>&1
    code=$?
    set -e
    echo "$code" > "$folder/exit_code.txt"
    test -s "$folder/result.json"
    FFMPEG=$($VLA -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')
    "$FFMPEG" -y -framerate 15 -pattern_type glob -i "$folder/video_frames/*.png" -c:v libx264 -pix_fmt yuv420p "$PROJECT/assets/videos/phase3_step7_oracle_${object}_$(printf '%02d' "$index").mp4" >"$folder/ffmpeg.log" 2>&1
  done
done

"$VLA" phase3/scripts/summarize_phase3_step7_grasp_oracle.py --result-dir "$RESULT"
nvidia-smi --query-gpu=name,memory.used,utilization.gpu --format=csv,noheader > "$RESULT/gpu_after.txt"
