#!/usr/bin/env bash
set -euo pipefail

LIBERO_ROOT=$(/root/autodl-tmp/miniforge3/envs/vla-intern/bin/python - <<'PY'
from pathlib import Path
import libero
print(Path(libero.__file__).resolve().parent / "libero")
PY
)
BDDL="$LIBERO_ROOT/bddl_files/libero_10/LIVING_ROOM_SCENE2_put_both_the_alphabet_soup_and_the_tomato_sauce_in_the_basket.bddl"

printf '%s\n' '=== PATHS ==='
printf 'libero_root=%s\nbddl=%s\n' "$LIBERO_ROOT" "$BDDL"
printf '%s\n' '=== BDDL ==='
sed -n '1,260p' "$BDDL"

printf '%s\n' '=== OBJECT SOURCE/XML HITS ==='
grep -RIn --include='*.py' --include='*.xml' \
  -e 'AlphabetSoup' -e 'TomatoSauce' -e 'alphabet_soup' -e 'tomato_sauce' -e 'basket' \
  "$LIBERO_ROOT" | head -n 400 || true

printf '%s\n' '=== SUCCESS SOURCE HITS ==='
grep -RIn --include='*.py' \
  -e 'check_success' -e '_check_success' -e 'class In' -e 'eval_predicate_fn' \
  "$LIBERO_ROOT" | head -n 400 || true

printf '%s\n' '=== CAMERA SOURCE/XML HITS ==='
grep -RIn --include='*.py' --include='*.xml' \
  -e 'camera_names' -e 'agentview' -e 'robot0_eye_in_hand' -e 'camera_pos' -e 'camera_quat' \
  -e 'camera_height' -e 'camera_width' "$LIBERO_ROOT" | head -n 400 || true

printf '%s\n' '=== CANDIDATE ASSET DIRECTORIES ==='
find "$LIBERO_ROOT" -type d \( \
  -iname '*alphabet*soup*' -o -iname '*tomato*sauce*' -o -iname '*basket*' -o -iname '*living*room*' \
\) -print | sort

printf '%s\n' '=== CANDIDATE ASSET FILES ==='
find "$LIBERO_ROOT" -type f \( \
  -iname '*alphabet*soup*' -o -iname '*tomato*sauce*' -o -iname '*basket*' -o \
  -iname '*.obj' -o -iname '*.stl' -o -iname '*.dae' \
\) -printf '%p\t%s bytes\n' | sort | head -n 500
