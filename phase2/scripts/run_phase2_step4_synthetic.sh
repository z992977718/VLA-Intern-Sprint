#!/usr/bin/env bash
set -euo pipefail
PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
RESULT="$PROJECT/results/phase2_step4"
source "$PROJECT/phase2/scripts/isaac_env.sh"
export PHASE2_STEP4_RESULT="$RESULT"
mkdir -p "$RESULT"
rm -f "$RESULT/frame_mapping_test.json" "$RESULT/gripper_mapping_test.json" \
      "$RESULT/synthetic_action_test.json" "$RESULT/synthetic_exception.txt"
/root/autodl-tmp/isaac_sim/venv/bin/python "$PROJECT/phase2/scripts/isaac_step4_synthetic.py" \
  > "$RESULT/synthetic_run.log" 2>&1
for file in frame_mapping_test.json gripper_mapping_test.json synthetic_action_test.json; do
  test -s "$RESULT/$file"
done
/root/autodl-tmp/isaac_sim/venv/bin/python - "$RESULT/synthetic_action_test.json" <<'PY'
import json, sys
status = json.load(open(sys.argv[1], encoding="utf-8"))
if status.get("pass") is not True:
    raise SystemExit("synthetic_action_test pass != true")
PY
