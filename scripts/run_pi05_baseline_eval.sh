#!/usr/bin/env bash
set -uo pipefail

source /root/autodl-tmp/vla_env.sh

VLA_PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
PYTHON=/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python
MODEL_DIR="$HF_HOME/pi05_libero_base"
EVAL_ROOT="$VLA_PROJECT/results/evaluation"
SMOKE_DIR="$EVAL_ROOT/pi05_pretrained_baseline_smoke"
FORMAL_DIR="$EVAL_ROOT/pi05_pretrained_baseline"

export HF_HUB_OFFLINE=1
export MUJOCO_GL=egl
export TOKENIZERS_PARALLELISM=false

if [[ -e "$SMOKE_DIR" || -e "$FORMAL_DIR" ]]; then
  echo "Refusing to overwrite an existing baseline evaluation." >&2
  exit 2
fi

if [[ ! -f "$MODEL_DIR/model.safetensors" || ! -f "$MODEL_DIR/config.json" ]]; then
  echo "Baseline checkpoint is incomplete: $MODEL_DIR" >&2
  exit 3
fi

ACTIVE_GPU_PROCESSES=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits | sed '/^[[:space:]]*$/d' | wc -l)
if (( ACTIVE_GPU_PROCESSES > 0 )); then
  echo "GPU already has an active compute process; refusing to overlap evaluation." >&2
  nvidia-smi >&2
  exit 4
fi

run_eval() {
  local output_dir=$1
  local episodes=$2
  local seed=$3
  local temporary_log="${output_dir}.log"

  "$PYTHON" "$VLA_PROJECT/scripts/run_pi05_profiled_eval.py" \
    --checkpoint "$MODEL_DIR" \
    --output-dir "$output_dir" \
    --suite libero_10 \
    --task-id 0 \
    --episodes "$episodes" \
    --seed "$seed" \
    --dtype bfloat16 \
    --n-action-steps 10 \
    --observation-height 360 \
    --observation-width 360 \
    2>&1 | tee "$temporary_log"
  local status=${PIPESTATUS[0]}
  if [[ -d "$output_dir" ]]; then
    mv "$temporary_log" "$output_dir/eval.log"
  fi
  return "$status"
}

echo "Starting one-episode pipeline smoke (seed 999)."
run_eval "$SMOKE_DIR" 1 999 || exit $?

echo "Pipeline smoke passed; starting formal 10-episode baseline (seeds 1000-1009)."
run_eval "$FORMAL_DIR" 10 1000 || exit $?

df -h "$VLA_PROJECT" > "$FORMAL_DIR/disk_after.txt"
echo "Baseline evaluation complete."
