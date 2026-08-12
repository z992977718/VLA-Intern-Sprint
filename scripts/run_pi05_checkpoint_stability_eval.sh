#!/usr/bin/env bash
set -uo pipefail

source /root/autodl-tmp/vla_env.sh

VLA_PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
PYTHON=/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python
CHECKPOINT_ROOT="$VLA_PROJECT/results/training/pi05_expert_first_stage_2k/run/checkpoints"
EVAL_ROOT="$VLA_PROJECT/results/evaluation"

export HF_HUB_OFFLINE=1
export MUJOCO_GL=egl
export TOKENIZERS_PARALLELISM=false

if [[ -e "$EVAL_ROOT/pi05_checkpoint_001000" || -e "$EVAL_ROOT/pi05_checkpoint_002000_30ep" ]]; then
  echo "Refusing to overwrite an existing stability evaluation." >&2
  exit 2
fi

for checkpoint in 001000 002000; do
  path="$CHECKPOINT_ROOT/$checkpoint/pretrained_model"
  if [[ ! -f "$path/config.json" || ! -f "$path/model.safetensors" ]]; then
    echo "Incomplete checkpoint: $path" >&2
    exit 3
  fi
done

ACTIVE_GPU_PROCESSES=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits | sed '/^[[:space:]]*$/d' | wc -l)
if (( ACTIVE_GPU_PROCESSES > 0 )); then
  echo "GPU already has an active compute process; refusing to overlap evaluation." >&2
  exit 4
fi

run_eval() {
  local checkpoint=$1
  local output_dir=$2
  local episodes=$3
  local seed=$4
  local temporary_log="${output_dir}.log"

  "$PYTHON" "$VLA_PROJECT/scripts/run_pi05_profiled_eval.py" \
    --checkpoint "$checkpoint" \
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
    df -h "$VLA_PROJECT" > "$output_dir/disk_after.txt"
  fi
  return "$status"
}

echo "Evaluating checkpoint 001000: 10 episodes, seeds 1000-1009."
run_eval \
  "$CHECKPOINT_ROOT/001000/pretrained_model" \
  "$EVAL_ROOT/pi05_checkpoint_001000" \
  10 \
  1000 || exit $?

echo "Evaluating checkpoint 002000: unified 30 episodes, seeds 1000-1029."
run_eval \
  "$CHECKPOINT_ROOT/002000/pretrained_model" \
  "$EVAL_ROOT/pi05_checkpoint_002000_30ep" \
  30 \
  1000 || exit $?

echo "Checkpoint stability evaluations complete."
