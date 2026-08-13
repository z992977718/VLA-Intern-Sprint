#!/usr/bin/env bash
set -euo pipefail

PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
RESULT_DIR="$PROJECT/results/phase2_step4"
VLA_PYTHON=/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python
ISAAC_PYTHON=/root/autodl-tmp/isaac_sim/venv/bin/python
export OMNI_KIT_ACCEPT_EULA=YES

mkdir -p "$RESULT_DIR/source_audit"

"$VLA_PYTHON" - <<'PY' > "$RESULT_DIR/source_audit/python_packages.txt"
import inspect
from pathlib import Path
import lerobot
import libero
import robosuite

for name, module in (("lerobot", lerobot), ("libero", libero), ("robosuite", robosuite)):
    print(name, Path(inspect.getfile(module)).resolve())
PY

"$VLA_PYTHON" - <<'PY' > "$RESULT_DIR/source_audit/action_runtime_audit.txt"
import inspect
import json
from pathlib import Path

import numpy as np
from safetensors.torch import load_file
from robosuite.controllers.osc import OperationalSpaceController
from robosuite.models.grippers.panda_gripper import PandaGripper

checkpoint = Path("/root/autodl-tmp/VLA-Intern-Sprint/results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model")
state = load_file(checkpoint / "policy_postprocessor_step_0_unnormalizer_processor.safetensors")
print("POSTPROCESSOR_TENSORS")
for key, value in state.items():
    print(key, value.tolist())
print("OSC_SOURCE", inspect.getfile(OperationalSpaceController))
print("OSC_SET_GOAL")
print(inspect.getsource(OperationalSpaceController.set_goal))
print("OSC_DELTA_TO_ABSOLUTE")
if hasattr(OperationalSpaceController, "delta_to_absolute_pose"):
    print(inspect.getsource(OperationalSpaceController.delta_to_absolute_pose))
else:
    print("METHOD_NOT_PRESENT_IN_INSTALLED_ROBOSUITE")
print("PANDA_GRIPPER_SOURCE", inspect.getfile(PandaGripper))
print(inspect.getsource(PandaGripper.format_action))
PY

cp "$PROJECT/results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model/policy_postprocessor.json" \
   "$RESULT_DIR/source_audit/policy_postprocessor.json"
cp "$PROJECT/results/training/pi05_expert_first_stage_2k/run/checkpoints/002000/pretrained_model/config.json" \
   "$RESULT_DIR/source_audit/checkpoint_config.json"
cp /root/autodl-tmp/cache/huggingface/lerobot/lerobot/libero/meta/info.json \
   "$RESULT_DIR/source_audit/dataset_info.json"
cp /root/autodl-tmp/cache/huggingface/lerobot/lerobot/libero/meta/stats.json \
   "$RESULT_DIR/source_audit/dataset_stats.json"

"$ISAAC_PYTHON" - <<'PY' > "$RESULT_DIR/source_audit/isaac_pink_api.txt" 2>&1
import inspect
from isaacsim import SimulationApp

app = SimulationApp({"headless": True})
try:
    import isaacsim.robot_motion.pink as pink
    print("PINK_FILE", inspect.getfile(pink))
    print("load_pink_supported_robot", inspect.signature(pink.load_pink_supported_robot))
    print("PinkIKController", inspect.signature(pink.PinkIKController))
    print("PinkIKController.forward", inspect.signature(pink.PinkIKController.forward))
finally:
    app.close()
PY

"$ISAAC_PYTHON" - <<'PY' > "$RESULT_DIR/source_audit/isaac_pink_source.txt" 2>&1
import inspect
import os
os.environ["OMNI_KIT_ACCEPT_EULA"] = "YES"
from isaacsim import SimulationApp
app = SimulationApp({"headless": True})
try:
    import isaacsim.robot_motion.pink as pink
    print(inspect.getsource(pink.PinkIKController.__init__))
    print(inspect.getsource(pink.PinkIKController.forward))
    root = os.path.dirname(inspect.getfile(pink))
    print("PINK_ROOT", root)
finally:
    app.close()
PY

find /root/autodl-tmp/cache/huggingface/lerobot -maxdepth 8 \
  \( -iname '*libero*' -o -iname 'meta' \) -print \
  > "$RESULT_DIR/source_audit/dataset_cache_paths.txt" 2>/dev/null || true

echo AUDIT_COMPLETE
