#!/usr/bin/env bash
set -euo pipefail

cd /root/autodl-tmp/VLA-Intern-Sprint
RESULT=results/phase3_step7/tomato_oracle_postfix
test ! -e "$RESULT"
mkdir -p "$RESULT"

cp phase3/scripts/isaac_step7_grasp_oracle.py "$RESULT/oracle_before_fix.py"
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader > "$RESULT/gpu_before_unit_tests.txt"

PYTHONPATH=phase3/scripts \
  /root/autodl-tmp/miniforge3/envs/vla-intern/bin/python \
  phase3/scripts/test_joint_safety_float_limits.py \
  --output "$RESULT/safety_unit_tests.json"

nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader > "$RESULT/gpu_after_unit_tests.txt"
/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python -m json.tool "$RESULT/safety_unit_tests.json" >/dev/null
echo UNIT_TESTS_COMPLETE
