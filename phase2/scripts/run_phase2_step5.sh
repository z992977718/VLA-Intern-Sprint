#!/usr/bin/env bash
set -euo pipefail
PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
RESULT="$PROJECT/results/phase2_step5"
CHECKPOINT="$PROJECT/results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model"
VLA=/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python
ISAAC=/root/autodl-tmp/isaac_sim/venv/bin/python
source "$PROJECT/phase2/scripts/isaac_env.sh"
mkdir -p "$RESULT" "$PROJECT/assets/images" "$PROJECT/assets/videos"
"$VLA" - "$PROJECT/results/phase2_step4/synthetic_action_test.json" "$PROJECT/results/phase2_step4/execution_error.json" <<'PY'
import json, sys
synthetic = json.load(open(sys.argv[1], encoding="utf-8"))
execution = json.load(open(sys.argv[2], encoding="utf-8"))
if synthetic.get("pass") is not True or execution.get("robot_moved") is not True:
    raise SystemExit("Step 4 runtime gate is not PASS")
PY
if test -e "$RESULT/run_status.json"; then echo '拒绝覆盖已完成的 Step 5'; exit 2; fi
rm -rf "$RESULT"/cycle_?? "$RESULT/frames" "$RESULT/video_frames"
rm -f "$RESULT"/{policy_ready,policy_complete,isaac_complete,isaac_failure}.json "$RESULT/stop"
cleanup(){
  touch "$RESULT/stop"
  for pid in ${ISAAC_PID:-} ${POLICY_PID:-} ${MONITOR_PID:-}; do kill -TERM "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT
echo 'timestamp,name,total_mib,used_mib,util_percent' > "$RESULT/gpu_timeseries.csv"
(while true; do nvidia-smi --query-gpu=timestamp,name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits >> "$RESULT/gpu_timeseries.csv"; sleep 1; done) &
MONITOR_PID=$!
(
  cd "$PROJECT"
  export PYTHONPATH="$PROJECT/lerobot/src:$PROJECT/phase2/scripts${PYTHONPATH:+:$PYTHONPATH}"
  source /root/autodl-tmp/vla_env.sh
  "$VLA" "$PROJECT/phase2/scripts/pi05_step5_policy_daemon.py" --checkpoint "$CHECKPOINT" --result-dir "$RESULT" --cycles 5
) > "$RESULT/policy.log" 2>&1 &
POLICY_PID=$!
for _ in $(seq 1 180); do
  test -s "$RESULT/policy_ready.json" && break
  kill -0 "$POLICY_PID" 2>/dev/null || break
  sleep 1
done
test -s "$RESULT/policy_ready.json"
export PHASE2_STEP5_RESULT="$RESULT" PHASE2_STEP5_ASSETS="$PROJECT/assets"
timeout 360 "$ISAAC" "$PROJECT/phase2/scripts/isaac_step5_closed_loop.py" > "$RESULT/isaac.log" 2>&1 &
ISAAC_PID=$!
wait "$ISAAC_PID"; ISAAC_PID=""
wait "$POLICY_PID"; POLICY_PID=""
test -s "$RESULT/isaac_complete.json"
test -s "$RESULT/policy_complete.json"
for i in 00 01 02 03 04; do test -s "$RESULT/cycle_$i.json"; done
"$VLA" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())' > "$RESULT/ffmpeg_path.txt"
"$(cat "$RESULT/ffmpeg_path.txt")" -y -framerate 10 -i "$RESULT/video_frames/frame_%04d.png" -c:v libx264 -pix_fmt yuv420p "$PROJECT/assets/videos/phase2_step5_closed_loop.mp4" > "$RESULT/ffmpeg.log" 2>&1
test -s "$PROJECT/assets/images/phase2_step5_start.png"
test -s "$PROJECT/assets/images/phase2_step5_end.png"
test -s "$PROJECT/assets/videos/phase2_step5_closed_loop.mp4"
kill -TERM "$MONITOR_PID" 2>/dev/null || true
wait "$MONITOR_PID" 2>/dev/null || true
MONITOR_PID=""
trap - EXIT
