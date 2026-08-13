#!/usr/bin/env bash
set -euo pipefail
BASE=/root/autodl-tmp/isaac_sim/venv/lib/python3.12/site-packages/isaacsim
RESULT=/root/autodl-tmp/VLA-Intern-Sprint/results/phase2_step4/source_audit/pink_installation.txt
{
  echo '=== isaacsim package top ==='
  ls -1 "$BASE" | head -n 100
  echo '=== bounded pink paths ==='
  find "$BASE/exts" "$BASE/extscache" "$BASE/apps" -maxdepth 4 -iname '*pink*' -print 2>/dev/null || true
  echo '=== installed distributions ==='
  /root/autodl-tmp/isaac_sim/venv/bin/pip list | grep -Ei 'isaac|pink|pinocchio|qpsolver|osqp' || true
  echo '=== pink python sources ==='
  find "$BASE/exts/isaacsim.robot_motion.pink" \
       "$BASE/exts/isaacsim.robot_motion.pink.examples" \
       -type f -name '*.py' -print | sort
} > "$RESULT"
cat "$RESULT"
