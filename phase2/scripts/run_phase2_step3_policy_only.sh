#!/usr/bin/env bash
set -euo pipefail

PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
RESULT_DIR="$PROJECT/results/phase2_step3"
CHECKPOINT="$PROJECT/results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model"
VLA_PYTHON=/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python

cd "$PROJECT"
export PYTHONPATH="$PROJECT/lerobot/src:$PROJECT/phase2/scripts${PYTHONPATH:+:$PYTHONPATH}"
source /root/autodl-tmp/vla_env.sh

"$VLA_PYTHON" "$PROJECT/phase2/scripts/run_pi05_step3_inference.py" \
  --checkpoint "$CHECKPOINT" \
  --result-dir "$RESULT_DIR" \
  --language "move the robot arm"

