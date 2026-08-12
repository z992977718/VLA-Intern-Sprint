#!/usr/bin/env bash
set -euo pipefail

source /root/autodl-tmp/VLA-Intern-Sprint/phase2/scripts/isaac_env.sh

"$ISAAC_ENV/bin/python" -m pip install --upgrade pip
"$ISAAC_ENV/bin/python" -m pip install --no-cache-dir \
  isaacsim==6.0.1.0 \
  isaacsim-app==6.0.1.0 \
  isaacsim-asset==6.0.1.0 \
  isaacsim-core==6.0.1.0 \
  isaacsim-cortex==6.0.1.0 \
  isaacsim-example==6.0.1.0 \
  isaacsim-robot==6.0.1.0 \
  isaacsim-replicator==6.0.1.0 \
  isaacsim-storage==6.0.1.0 \
  isaacsim-test==6.0.1.0 \
  isaacsim-ros2==6.0.1.0 \
  isaacsim-extscache-kit==6.0.1.0 \
  isaacsim-extscache-kit-sdk==6.0.1.0 \
  isaacsim-extscache-physics==6.0.1.0 \
  --extra-index-url https://pypi.nvidia.com

"$ISAAC_ENV/bin/python" -m pip check
"$ISAAC_ENV/bin/python" -m pip show isaacsim isaacsim-app isaacsim-asset isaacsim-core isaacsim-robot isaacsim-ros2
