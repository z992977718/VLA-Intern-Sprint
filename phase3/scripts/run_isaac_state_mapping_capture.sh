#!/usr/bin/env bash
set -euo pipefail

PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
RESULT="$PROJECT/results/phase3_step7/state_mapping_fix"
ISAAC=/root/autodl-tmp/isaac_sim/venv/bin/python

cd "$PROJECT"
source phase2/scripts/isaac_env.sh
export PYTHONPATH="$PROJECT/phase3/scripts:$PROJECT/phase2/scripts"

for pose_set in calibration holdout; do
  output="$RESULT/isaac_${pose_set}.json"
  log="$RESULT/isaac_${pose_set}.log"
  if [[ -e "$output" ]]; then
    echo "Refusing to overwrite $output" >&2
    exit 1
  fi
  "$ISAAC" phase3/scripts/capture_state_mapping_fix.py \
    --mode isaac --set "$pose_set" --output "$output" >"$log" 2>&1
done
