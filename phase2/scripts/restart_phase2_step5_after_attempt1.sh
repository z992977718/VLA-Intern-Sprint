#!/usr/bin/env bash
set -euo pipefail
RESULT=/root/autodl-tmp/VLA-Intern-Sprint/results/phase2_step5
if pgrep -af 'run_phase2_step5|pi05_step5_policy_daemon|isaac_step5_closed_loop' | grep -v 'pgrep -af' >/dev/null; then
  echo '已有 Step 5 进程，拒绝重复启动'
  exit 3
fi
mkdir -p "$RESULT/attempt_001_before_cycle0"
for file in isaac_failure.json isaac.log policy.log gpu_timeseries.csv policy_ready.json; do
  test -e "$RESULT/$file" && mv "$RESULT/$file" "$RESULT/attempt_001_before_cycle0/"
done
rm -f "$RESULT/stop"
nohup bash /root/autodl-tmp/VLA-Intern-Sprint/phase2/scripts/run_phase2_step5.sh \
  > "$RESULT/run.log" 2>&1 < /dev/null &
echo $! > "$RESULT/wrapper.pid"
echo "wrapper_pid=$!"
