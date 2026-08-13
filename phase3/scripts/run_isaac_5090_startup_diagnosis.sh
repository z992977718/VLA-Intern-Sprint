#!/usr/bin/env bash
# No wall-clock timeout: each isolated mode is allowed to reach its real ready marker.
set -euo pipefail
PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
RESULT="$PROJECT/results/isaac_5090_startup_diagnosis_20260813_attempt03"
ISAAC=/root/autodl-tmp/isaac_sim/venv/bin/python
test ! -e "$RESULT"
mkdir -p "$RESULT"
source "$PROJECT/phase2/scripts/isaac_env.sh"
nvidia-smi > "$RESULT/environment.txt"
for mode in base single_camera dual_camera ros2_only; do
  echo "mode=$mode start=$(date -Is)" | tee "$RESULT/$mode.launcher.txt"
  "$ISAAC" "$PROJECT/phase3/scripts/diagnose_isaac_5090_startup.py" \
    --mode "$mode" --output-dir "$RESULT/$mode" \
    > "$RESULT/$mode.stdout_stderr.log" 2>&1
  echo "mode=$mode finish=$(date -Is)" >> "$RESULT/$mode.launcher.txt"
done
python3 - "$RESULT" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
summary = {mode: json.loads((root / mode / 'result.json').read_text()) for mode in ('base', 'single_camera', 'dual_camera', 'ros2_only')}
summary['all_pass'] = all(item['pass'] for item in summary.values())
(root / 'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
PY
