#!/usr/bin/env bash
set -uo pipefail

cd /root/autodl-tmp/VLA-Intern-Sprint

output_dir="results/phase3_step7/tomato_safety_diagnostic"
if [[ -e "$output_dir" ]]; then
  echo "Refusing to overwrite existing diagnostic directory: $output_dir" >&2
  exit 91
fi

source phase2/scripts/isaac_env.sh
export PYTHONPATH="$PWD/phase2/scripts:$PWD/phase3/scripts"

/root/autodl-tmp/isaac_sim/venv/bin/python -c \
  'import ast, pathlib; ast.parse(pathlib.Path("phase3/scripts/isaac_step7_tomato_safety_diagnostic.py").read_text()); print("REMOTE_AST_PARSE=PASS")'

sha256sum \
  phase3/scripts/isaac_step7_grasp_oracle.py \
  phase3/scripts/isaac_step7_tomato_safety_diagnostic.py

timeout --signal=INT --kill-after=30s 600s \
  /root/autodl-tmp/isaac_sim/venv/bin/python \
  phase3/scripts/isaac_step7_tomato_safety_diagnostic.py \
  --output-dir "$output_dir"
diagnostic_exit=$?

echo "DIAGNOSTIC_EXIT=$diagnostic_exit"
if [[ -d "$output_dir" ]]; then
  find "$output_dir" -maxdepth 1 -type f -printf '%f %s bytes\n' | sort
fi

nvidia-smi \
  --query-gpu=name,memory.total,memory.used,utilization.gpu \
  --format=csv,noheader

sha256sum \
  results/phase3_step7/grasp_oracle/grasp_success_summary.json \
  results/phase3_step7/grasp_oracle/tomato_00/result.json \
  results/phase3_step7/grasp_oracle/tomato_01/result.json \
  results/phase3_step7/grasp_oracle/tomato_02/result.json

exit "$diagnostic_exit"
