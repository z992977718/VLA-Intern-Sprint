#!/usr/bin/env bash
set -uo pipefail

source /root/autodl-tmp/vla_env.sh

VLA_PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
LEROBOT_DIR="$VLA_PROJECT/lerobot"
RESULT_DIR="$VLA_PROJECT/results/training/pi05_expert_first_stage_2k"
OUTPUT_DIR="$RESULT_DIR/run"
MODEL_DIR="$HF_HOME/pi05_libero_base"
DATASET_DIR="$HF_LEROBOT_HOME/lerobot/libero"
PYTHON=/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python

export PI05_SMOKE_RESULT_DIR="$RESULT_DIR"
export HF_HUB_OFFLINE=1
export WANDB_MODE=disabled
export MUJOCO_GL=egl

if [[ -e "$RESULT_DIR" ]]; then
  echo "Refusing to overwrite existing formal training result: $RESULT_DIR" >&2
  exit 2
fi
mkdir -p "$RESULT_DIR"

for required in \
  "$MODEL_DIR/config.json" \
  "$MODEL_DIR/model.safetensors" \
  "$DATASET_DIR/meta/info.json"; do
  if [[ ! -f "$required" ]]; then
    echo "Missing required file: $required" >&2
    exit 3
  fi
done

AVAILABLE_KIB=$(df --output=avail "$VLA_PROJECT" | tail -1)
if (( AVAILABLE_KIB < 60 * 1024 * 1024 )); then
  echo "Less than 60 GiB free; refusing to start checkpoint-producing run." >&2
  exit 4
fi

ACTIVE_GPU_PROCESSES=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits | sed '/^[[:space:]]*$/d' | wc -l)
if (( ACTIVE_GPU_PROCESSES > 0 )); then
  echo "GPU already has an active compute process; refusing to overlap runs." >&2
  nvidia-smi >&2
  exit 5
fi

cd "$LEROBOT_DIR"
{
  date -Is
  uname -a
  "$PYTHON" --version
  "$PYTHON" -c "import torch, lerobot, libero; print('torch:', torch.__version__); print('torch_cuda:', torch.version.cuda); print('lerobot:', lerobot.__version__); print('libero:', libero.__file__)"
  git rev-parse HEAD
  df -h "$VLA_PROJECT"
} > "$RESULT_DIR/preflight.txt" 2>&1
nvidia-smi > "$RESULT_DIR/nvidia_smi_before.txt"

cat > "$RESULT_DIR/training_config.txt" <<'EOF'
dataset=lerobot/libero
dataset_revision=a1aaacb7f6cd6ee5fb43120f673cebb0cfea7dd4
pretrained_policy=lerobot/pi05_libero_base (local verified snapshot)
steps=2000
batch_size=1
precision=bfloat16
accelerator_mixed_precision=bf16
n_action_steps=10
normalization=MEAN_STD for ACTION and STATE; IDENTITY for VISUAL
gradient_checkpointing=true
train_expert_only=true
freeze_vision_encoder=true
compile_model=false
ema=false
num_workers=1
save_checkpoint=true
save_freq=1000
expected_checkpoints=001000,002000
env_eval_freq=0
eval_steps=0
seed=1000
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
    sleep 2
  done
) >> "$RESULT_DIR/nvidia_smi_timeseries.csv" 2>&1 &
SAMPLER_PID=$!

cleanup_sampler() {
  kill "$SAMPLER_PID" 2>/dev/null || true
  wait "$SAMPLER_PID" 2>/dev/null || true
}
trap cleanup_sampler EXIT

"$PYTHON" "$VLA_PROJECT/scripts/profile_pi05_smoke.py" \
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
  --job_name=pi05_libero_expert_first_stage_2k \
  --batch_size=1 \
  --num_workers=1 \
  --steps=2000 \
  --log_freq=10 \
  --save_checkpoint=true \
  --save_freq=1000 \
  --env_eval_freq=0 \
  --eval_steps=0 \
  --wandb.enable=false \
  --seed=1000 \
  2>&1 | tee "$RESULT_DIR/train.log"
TRAIN_STATUS=${PIPESTATUS[0]}

cleanup_sampler
trap - EXIT
nvidia-smi > "$RESULT_DIR/nvidia_smi_after.txt"
df -h "$VLA_PROJECT" > "$RESULT_DIR/disk_after.txt"
printf '%s\n' "$TRAIN_STATUS" > "$RESULT_DIR/exit_code.txt"

"$PYTHON" "$VLA_PROJECT/scripts/summarize_pi05_sanity.py" "$RESULT_DIR" || true
find "$OUTPUT_DIR/checkpoints" -maxdepth 2 -type f -printf '%P %s\n' | sort > "$RESULT_DIR/checkpoint_manifest.txt" 2>/dev/null || true

exit "$TRAIN_STATUS"
