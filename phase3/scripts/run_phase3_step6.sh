#!/usr/bin/env bash
set -euo pipefail

PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
RESULT="$PROJECT/results/phase3_step6"
CHECKPOINT="$PROJECT/results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model"
VLA=/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python
ISAAC=/root/autodl-tmp/isaac_sim/venv/bin/python
export PYTHONPATH="$PROJECT/lerobot/src:$PROJECT/phase2/scripts:$PROJECT/phase3/scripts${PYTHONPATH:+:$PYTHONPATH}"
source "$PROJECT/phase2/scripts/isaac_env.sh"
source /root/autodl-tmp/vla_env.sh

test -s "$RESULT/scene_gate_state00_dynamic/scene_gate.json"
test -s "$RESULT/scene_gate_state00_dynamic/success_detector_tests.json"
"$VLA" - "$RESULT/scene_gate_state00_dynamic/scene_gate.json" "$RESULT/scene_gate_state00_dynamic/success_detector_tests.json" <<'PY'
import json,sys
for path in sys.argv[1:]:
    if json.load(open(path, encoding="utf-8")).get("pass") is not True:
        raise SystemExit(f"gate is not PASS: {path}")
PY
test -d "$CHECKPOINT"
if test -e "$RESULT/run_complete.json"; then
    echo "Refusing to overwrite completed Step 6"
    exit 2
fi
for episode in 00 01 02; do
    if test -e "$RESULT/episode_${episode}/episode_complete.json"; then
        echo "Refusing to overwrite episode_${episode}"
        exit 2
    fi
done

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
        nvidia-smi --query-gpu=timestamp,name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits >> "$RESULT/gpu_timeseries.csv"
        sleep 1
    done
) &
MONITOR_PID=$!

"$VLA" "$PROJECT/phase3/scripts/pi05_step6_policy_daemon.py" \
    --checkpoint "$CHECKPOINT" --result-dir "$RESULT" --episodes 3 --max-cycles 100 \
    --language "put both the alphabet soup and the tomato sauce in the basket" \
    > "$RESULT/policy_step6.log" 2>&1 &
POLICY_PID=$!
for _ in $(seq 1 240); do
    test -s "$RESULT/policy_ready.json" && break
    kill -0 "$POLICY_PID" 2>/dev/null || break
    sleep 1
done
test -s "$RESULT/policy_ready.json"

for index in 0 1 2; do
    episode=$(printf '%02d' "$index")
    mkdir -p "$RESULT/episode_${episode}"
    set +e
    timeout 1000 "$ISAAC" "$PROJECT/phase3/scripts/isaac_step6_episode.py" \
        --episode-index "$index" --result-dir "$RESULT/episode_${episode}" \
        > "$RESULT/episode_${episode}/isaac.log" 2>&1
    ISAAC_EXIT=$?
    set -e
    echo "$ISAAC_EXIT" > "$RESULT/episode_${episode}/isaac_exit_code.txt"
    test -s "$RESULT/episode_${episode}/episode_complete.json"
    FFMPEG=$("$VLA" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')
    "$FFMPEG" -y -framerate 10 -i "$RESULT/episode_${episode}/video_frames/frame_%05d.png" \
        -c:v libx264 -pix_fmt yuv420p "$PROJECT/assets/videos/phase3_step6_ep${episode}.mp4" \
        > "$RESULT/episode_${episode}/ffmpeg.log" 2>&1
    test -s "$PROJECT/assets/videos/phase3_step6_ep${episode}.mp4"
done

wait "$POLICY_PID"
POLICY_PID=""
test -s "$RESULT/policy_complete.json"
"$VLA" "$PROJECT/phase3/scripts/summarize_phase3_step6.py" > "$RESULT/summary.log" 2>&1
test -s "$RESULT/summary.json"
kill -TERM "$MONITOR_PID" 2>/dev/null || true
wait "$MONITOR_PID" 2>/dev/null || true
MONITOR_PID=""
"$VLA" - <<'PY'
from pathlib import Path
import json
p=Path('/root/autodl-tmp/VLA-Intern-Sprint/results/phase3_step6')
s=json.load(open(p/'summary.json', encoding='utf-8'))
(p/'run_complete.json').write_text(json.dumps({
  'pass': s['experimental_pipeline_pass'],
  'task_success_count': s['task_success_count'],
  'episodes': 3,
  'gpu_idle_requested_after_run': True,
}, indent=2)+'\n', encoding='utf-8')
PY
trap - EXIT
