#!/usr/bin/env bash
set -euo pipefail

readonly ICD_DIR="/etc/vulkan/icd.d"
readonly ICD_FILE="${ICD_DIR}/my_nvidia_icd.json"
readonly EGL_LIBRARY="/lib/x86_64-linux-gnu/libEGL_nvidia.so.0"
readonly SUMMARY_FILE="/tmp/vulkaninfo_egl_summary.txt"

if [[ ! -r "${EGL_LIBRARY}" ]]; then
  echo "ERROR: ${EGL_LIBRARY} is missing or unreadable" >&2
  exit 1
fi

mkdir -p "${ICD_DIR}"
printf '%s\n' \
  '{' \
  '    "file_format_version" : "1.0.1",' \
  '    "ICD": {' \
  '        "library_path": "/lib/x86_64-linux-gnu/libEGL_nvidia.so.0",' \
  '        "api_version" : "1.4.329"' \
  '    }' \
  '}' > "${ICD_FILE}"

python3 -m json.tool "${ICD_FILE}" >/dev/null

echo "=== NEW ICD ==="
cat "${ICD_FILE}"
echo "=== ORIGINAL ICD (UNCHANGED) ==="
cat "${ICD_DIR}/nvidia_icd.json"

set +e
VK_ICD_FILENAMES="${ICD_FILE}" vulkaninfo --summary >"${SUMMARY_FILE}" 2>&1
vulkan_exit=$?
set -e

echo "=== VULKAN SUMMARY ==="
grep -E 'Vulkan Instance Version|deviceName|deviceType|driverName|driverInfo|apiVersion|ERROR|error:' \
  "${SUMMARY_FILE}" | head -80 || true
echo "VULKANINFO_EXIT=${vulkan_exit}"

exit "${vulkan_exit}"
