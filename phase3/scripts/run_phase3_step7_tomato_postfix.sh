#!/usr/bin/env bash
set -euo pipefail

PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
RESULT="$PROJECT/results/phase3_step7/tomato_oracle_postfix"
ISAAC=/root/autodl-tmp/isaac_sim/venv/bin/python
VLA=/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python

cd "$PROJECT"
source phase2/scripts/isaac_env.sh
export PYTHONPATH="$PROJECT/phase2/scripts:$PROJECT/phase3/scripts${PYTHONPATH:+:$PYTHONPATH}"

test -d "$RESULT"
test -s "$RESULT/safety_unit_tests.json"
"$VLA" -c 'import json; assert json.load(open("results/phase3_step7/tomato_oracle_postfix/safety_unit_tests.json"))["all_pass"] is True'
for index in 0 1 2; do
  test ! -e "$RESULT/trial_$(printf '%02d' "$index")"
done

set +e
diff -u "$RESULT/oracle_before_fix.py" phase3/scripts/isaac_step7_grasp_oracle.py > "$RESULT/safety_fix.diff"
diff_code=$?
set -e
test "$diff_code" -eq 0 -o "$diff_code" -eq 1

{
  echo "Isaac: $($ISAAC -c 'import isaacsim; print(isaacsim.__file__)')"
  echo "GPU: $(nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader)"
  echo "Scene/controller/trajectory/physics/success metric: unchanged from Phase 3 Step 7C"
  echo "Policy: NOT USED"
} > "$RESULT/environment.txt"

for index in 0 1 2; do
  folder="$RESULT/trial_$(printf '%02d' "$index")"
  set +e
  timeout --signal=INT --kill-after=30s 720s "$ISAAC" \
    phase3/scripts/isaac_step7_grasp_oracle.py \
    --object tomato \
    --trial-index "$index" \
    --output-dir "$folder" \
    >"$RESULT/trial_$(printf '%02d' "$index").launch.log" 2>&1
  code=$?
  set -e
  echo "$code" > "$folder/exit_code.txt"
  test -s "$folder/result.json"
  FFMPEG=$($VLA -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')
  "$FFMPEG" -y -framerate 15 -pattern_type glob -i "$folder/video_frames/*.png" \
    -c:v libx264 -pix_fmt yuv420p \
    "$PROJECT/assets/videos/phase3_step7_oracle_tomato_postfix_$(printf '%02d' "$index").mp4" \
    >"$folder/ffmpeg.log" 2>&1
done

"$VLA" phase3/scripts/summarize_phase3_step7_tomato_postfix.py --result-dir "$RESULT"
nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader > "$RESULT/gpu_after.txt"
