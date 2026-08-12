#!/usr/bin/env bash
set -uo pipefail

source /root/autodl-tmp/vla_env.sh

VLA_PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
LEROBOT_DIR="$VLA_PROJECT/lerobot"
RESULT_DIR="$VLA_PROJECT/results/training/pi05_sanity_new_server"
OUTPUT_DIR="$RESULT_DIR/run"
MODEL_DIR="$HF_HOME/pi05_libero_base"
DATASET_DIR="$HF_LEROBOT_HOME/lerobot/libero"
PYTHON=/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python

export PI05_SMOKE_RESULT_DIR="$RESULT_DIR"
export HF_HUB_OFFLINE=1
export WANDB_MODE=disabled
export MUJOCO_GL=egl

mkdir -p "$RESULT_DIR"

if [[ -e "$OUTPUT_DIR" || -e "$RESULT_DIR/torch_step_metrics.jsonl" ]]; then
  echo "Refusing to overwrite an existing sanity run." >&2
  exit 2
fi

cd "$LEROBOT_DIR"

{
  date -Is
  uname -a
  "$PYTHON" --version
  "$PYTHON" -c "import torch, lerobot, libero; print('torch:', torch.__version__); print('torch_cuda:', torch.version.cuda); print('lerobot:', lerobot.__version__); print('libero:', libero.__file__)"
  git rev-parse HEAD
} > "$RESULT_DIR/environment.txt" 2>&1

nvidia-smi > "$RESULT_DIR/gpu_info.txt"
df -h > "$RESULT_DIR/disk_info.txt"

cat > "$RESULT_DIR/training_config.txt" <<'EOF'
steps=20
batch_size=1
precision=bfloat16
accelerator_mixed_precision=bf16
gradient_checkpointing=true
train_expert_only=true
freeze_vision_encoder=true
compile_model=false
ema=false
num_workers=1
save_checkpoint=true
save_freq=0 (final checkpoint only)
env_eval_freq=0
eval_steps=0
EOF

printf '%s\n' \
  'timestamp_utc,index,name,memory_used_mib,memory_total_mib,utilization_gpu_percent,power_draw_watts,temperature_c' \
  > "$RESULT_DIR/nvidia_smi_timeseries.csv"

(
  while true; do
    printf '%s,' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    nvidia-smi \
      --query-gpu=index,name,memory.used,memory.total,utilization.gpu,power.draw,temperature.gpu \
      --format=csv,noheader,nounits
    sleep 1
  done
) >> "$RESULT_DIR/nvidia_smi_timeseries.csv" 2>&1 &
SAMPLER_PID=$!

cleanup_sampler() {
  kill "$SAMPLER_PID" 2>/dev/null || true
  wait "$SAMPLER_PID" 2>/dev/null || true
}
trap cleanup_sampler EXIT

"$PYTHON" \
  "$VLA_PROJECT/scripts/profile_pi05_smoke.py" \
  --dataset.repo_id=lerobot/libero \
  --dataset.root="$DATASET_DIR" \
  --dataset.revision=a1aaacb7f6cd6ee5fb43120f673cebb0cfea7dd4 \
  --dataset.video_backend=torchcodec \
  --policy.type=pi05 \
  --policy.pretrained_path="$MODEL_DIR" \
  --policy.normalization_mapping='{"ACTION": "MEAN_STD", "STATE": "MEAN_STD", "VISUAL": "IDENTITY"}' \
  --policy.n_action_steps=10 \
  --policy.empty_cameras=1 \
  --policy.freeze_vision_encoder=true \
  --policy.train_expert_only=true \
  --policy.gradient_checkpointing=true \
  --policy.dtype=bfloat16 \
  --policy.compile_model=false \
  --policy.device=cuda \
  --policy.push_to_hub=false \
  --accelerator.mixed_precision=bf16 \
  --accelerator.gradient_accumulation.steps=1 \
  --ema.enable=false \
  --output_dir="$OUTPUT_DIR" \
  --job_name=pi05_libero_rtx6000d_sanity \
  --batch_size=1 \
  --num_workers=1 \
  --steps=20 \
  --log_freq=1 \
  --save_checkpoint=true \
  --save_freq=0 \
  --env_eval_freq=0 \
  --eval_steps=0 \
  --wandb.enable=false \
  --seed=1000 \
  2>&1 | tee "$RESULT_DIR/train.log"
TRAIN_STATUS=${PIPESTATUS[0]}

cleanup_sampler
trap - EXIT
nvidia-smi > "$RESULT_DIR/nvidia_smi_after.txt"
printf '%s\n' "$TRAIN_STATUS" > "$RESULT_DIR/exit_code.txt"

"$PYTHON" "$VLA_PROJECT/scripts/summarize_pi05_sanity.py" "$RESULT_DIR" || true

exit "$TRAIN_STATUS"
