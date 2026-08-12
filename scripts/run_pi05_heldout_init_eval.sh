#!/usr/bin/env bash
set -uo pipefail

source /root/autodl-tmp/vla_env.sh

VLA_PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
PYTHON=/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python
CHECKPOINT="$VLA_PROJECT/results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model"
OUTPUT_DIR="$VLA_PROJECT/results/evaluation/generalization/heldout_initial_states"
TEMP_LOG="${OUTPUT_DIR}.log"

export HF_HUB_OFFLINE=1
export MUJOCO_GL=egl
export TOKENIZERS_PARALLELISM=false

if [[ -e "$OUTPUT_DIR" ]]; then
  echo "Refusing to overwrite existing held-out initial-state evaluation: $OUTPUT_DIR" >&2
  exit 2
fi
if [[ ! -f "$CHECKPOINT/config.json" || ! -f "$CHECKPOINT/model.safetensors" ]]; then
  echo "Incomplete checkpoint: $CHECKPOINT" >&2
  exit 3
fi

ACTIVE_GPU_PROCESSES=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits | sed '/^[[:space:]]*$/d' | wc -l)
if (( ACTIVE_GPU_PROCESSES > 0 )); then
  echo "GPU already has an active compute process; refusing to overlap evaluation." >&2
  exit 4
fi

mkdir -p "$(dirname "$OUTPUT_DIR")"
"$PYTHON" "$VLA_PROJECT/scripts/run_pi05_profiled_eval.py" \
  --checkpoint "$CHECKPOINT" \
  --output-dir "$OUTPUT_DIR" \
  --suite libero_10 \
  --task-id 0 \
  --episodes 20 \
  --seed 1030 \
  --init-state-start 30 \
  --dtype bfloat16 \
  --n-action-steps 10 \
  --observation-height 360 \
  --observation-width 360 \
  2>&1 | tee "$TEMP_LOG"
STATUS=${PIPESTATUS[0]}

if [[ -d "$OUTPUT_DIR" ]]; then
  mv "$TEMP_LOG" "$OUTPUT_DIR/eval.log"
  df -h "$VLA_PROJECT" > "$OUTPUT_DIR/disk_after.txt"
fi
exit "$STATUS"
