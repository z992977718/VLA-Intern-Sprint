#!/usr/bin/env bash
set -euo pipefail

PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
RESULT="$PROJECT/results/phase3_step7/arm_gripper_decoupling"
TRIAL="$RESULT/diagnostic_trial"
ISAAC=/root/autodl-tmp/isaac_sim/venv/bin/python
VLA=/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python

cd "$PROJECT"
source phase2/scripts/isaac_env.sh
export PYTHONPATH="$PROJECT/phase2/scripts:$PROJECT/phase3/scripts${PYTHONPATH:+:$PYTHONPATH}"

test -d "$RESULT"
test -s "$RESULT/unit_tests.json"
test -s "$RESULT/franka_arm_only.urdf"
test ! -e "$TRIAL"
test ! -e "$RESULT/diagnostic_launch.log"
"$VLA" -c 'import json; data=json.load(open("results/phase3_step7/arm_gripper_decoupling/unit_tests.json")); assert data["all_pass"] is True; assert all(data["tests"].values())'

sha256sum -c "$RESULT/frozen_assets_before.sha256"
diff -u "$RESULT/oracle_before_arm_gripper_fix.py" phase3/scripts/isaac_step7_grasp_oracle.py > "$RESULT/arm_gripper_decoupling_fix.diff" || test "$?" -eq 1

"$VLA" -c 'import json, pathlib; p=pathlib.Path("results/phase3_step7/arm_gripper_decoupling/diagnostic_config.json"); data={"trial_type":"DIAGNOSTIC / NOT COUNTED","authorized_trial_count":1,"object":"tomato_sauce","initial_state_id":0,"scene":"Phase 3 Step 6/7C scene","pre_grasp_clearance_m":0.085,"grasp_top_clearance_m":0.010,"lift_delta_m":0.060,"stage_steps":{"approach":240,"descent":200,"close_settle":180,"lift":240,"hold":180},"pink_costs":{"position":5.0,"orientation":0.25,"posture":0.005},"solver":"osqp","physics_changed":False,"safety_changed":False,"success_metric_changed":False,"only_architecture_change":"PINK 9D arm+finger -> 7D arm-only","pi05_called":False}; p.write_text(json.dumps(data,indent=2)+"\n")'

nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu --format=csv,noheader > "$RESULT/gpu_before_diagnostic.txt"
set +e
timeout --signal=INT --kill-after=30s 900s "$ISAAC" \
  phase3/scripts/isaac_step7_grasp_oracle.py \
  --object tomato \
  --trial-index 0 \
  --diagnostic \
  --arm-only-urdf "$RESULT/franka_arm_only.urdf" \
  --output-dir "$TRIAL" \
  >"$RESULT/diagnostic_launch.log" 2>&1
code=$?
set -e
printf '%s\n' "$code" > "$RESULT/diagnostic_exit_code.txt"

"$VLA" phase3/scripts/summarize_arm_gripper_decoupling.py --result-dir "$RESULT"
nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu --format=csv,noheader > "$RESULT/gpu_after_diagnostic.txt"
sha256sum \
  "$PROJECT/results/phase3_step7/grasp_oracle/grasp_success_summary.json" \
  "$PROJECT/results/phase3_step7/grasp_oracle/tomato_00/result.json" \
  "$PROJECT/results/phase3_step7/grasp_oracle/tomato_01/result.json" \
  "$PROJECT/results/phase3_step7/grasp_oracle/tomato_02/result.json" \
  > "$RESULT/frozen_assets_after.sha256"
diff -u "$RESULT/frozen_assets_before.sha256" "$RESULT/frozen_assets_after.sha256"

echo STEP_7C_5_SINGLE_DIAGNOSTIC_COMPLETE
