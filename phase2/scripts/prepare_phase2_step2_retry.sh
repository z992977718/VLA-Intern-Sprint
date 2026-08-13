#!/usr/bin/env bash
set -euo pipefail

readonly PROJECT_ROOT="/root/autodl-tmp/VLA-Intern-Sprint"
readonly RESULT_DIR="${PROJECT_ROOT}/results/phase2_step2"
readonly ARCHIVE_NAME="${1:-attempt_archive}"
readonly ARCHIVE_DIR="${RESULT_DIR}/${ARCHIVE_NAME}"

mkdir -p "${ARCHIVE_DIR}"
find "${RESULT_DIR}" -maxdepth 1 -type f -exec cp -p '{}' "${ARCHIVE_DIR}/" ';'

if pgrep -f '[i]saac_franka_camera_ros2.py' >/dev/null; then
  echo "ERROR: an Isaac Step 2 process is already running" >&2
  exit 1
fi

chmod 755 "${PROJECT_ROOT}/phase2/scripts/isaac_env.sh"
source "${PROJECT_ROOT}/phase2/scripts/isaac_env.sh"

echo "ARCHIVE_FILES=$(find "${ARCHIVE_DIR}" -maxdepth 1 -type f | wc -l)"
echo "VK_ICD_FILENAMES=${VK_ICD_FILENAMES}"
echo "XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR}"
