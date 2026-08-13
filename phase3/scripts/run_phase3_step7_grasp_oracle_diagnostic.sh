#!/usr/bin/env bash
set -euo pipefail
PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
RESULT="$PROJECT/results/phase3_step7/grasp_oracle_diagnostic"
ISAAC=/root/autodl-tmp/isaac_sim/venv/bin/python
cd "$PROJECT"
source phase2/scripts/isaac_env.sh
export PYTHONPATH="$PROJECT/phase2/scripts:$PROJECT/phase3/scripts${PYTHONPATH:+:$PYTHONPATH}"
test ! -e "$RESULT" || { echo "Refusing to overwrite $RESULT" >&2; exit 2; }
mkdir -p "$RESULT"
timeout 720 "$ISAAC" phase3/scripts/isaac_step7_grasp_oracle.py \
  --object alphabet --trial-index 0 --diagnostic --output-dir "$RESULT/alphabet_00" \
  > "$RESULT/diagnostic.launch.log" 2>&1
echo "DIAGNOSTIC / NOT COUNTED" > "$RESULT/status.txt"
