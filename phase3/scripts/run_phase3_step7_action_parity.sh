#!/usr/bin/env bash
set -euo pipefail

project=/root/autodl-tmp/VLA-Intern-Sprint
result="$project/results/phase3_step7/action_parity_attempt2"
test ! -e "$result" || { echo "refusing to overwrite $result" >&2; exit 1; }
mkdir -p "$result"

printf 'Step 7A action parity audit\nNo Pi0.5 inference, task rollout, or training.\n' > "$result/environment.txt"
source /root/autodl-tmp/vla_env.sh
export PYTHONPATH="$project/lerobot/src:$project/phase3/scripts:$project/phase2/scripts${PYTHONPATH:+:$PYTHONPATH}"
"/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python" "$project/phase3/scripts/measure_libero_action_parity.py" --output "$result/libero_all.json" 2>&1 | tee "$result/libero_stdout_stderr.log"

source "$project/phase2/scripts/isaac_env.sh"
for case in +X -X +Y -Y +Z -Z +Rx -Rx +Ry -Ry +Rz -Rz open close; do
  "/root/autodl-tmp/isaac_sim/venv/bin/python" "$project/phase3/scripts/measure_isaac_action_parity.py" --case="$case" --output "$result/isaac_${case}.json" 2>&1 | tee "$result/isaac_${case}.log"
done

"/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python" "$project/phase3/scripts/compare_action_parity.py" --dir "$result"
printf '{"completed": true, "pi05_called": false, "task_rollout": false, "training": false}\n' > "$result/run_status.json"
