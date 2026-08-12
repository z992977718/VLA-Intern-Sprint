#!/usr/bin/env bash
export ISAAC_ENV=/root/autodl-tmp/isaac_sim/venv
export ISAAC_PROJECT=/root/autodl-tmp/VLA-Intern-Sprint
export PIP_CACHE_DIR=/root/autodl-tmp/isaac_cache/pip
export XDG_CACHE_HOME=/root/autodl-tmp/isaac_cache/xdg
export XDG_DATA_HOME=/root/autodl-tmp/isaac_cache/data
export XDG_CONFIG_HOME=/root/autodl-tmp/isaac_cache/config
export TMPDIR=/root/autodl-tmp/isaac_cache/tmp
export OMNI_KIT_ACCEPT_EULA=YES
export ROS_DISTRO=humble
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DOMAIN_ID=42
ISAAC_ROS_LIB="$ISAAC_ENV/lib/python3.12/site-packages/isaacsim/exts/isaacsim.ros2.core/humble/lib"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}:$ISAAC_ROS_LIB"
mkdir -p "$PIP_CACHE_DIR" "$XDG_CACHE_HOME" "$XDG_DATA_HOME" "$XDG_CONFIG_HOME" "$TMPDIR"
