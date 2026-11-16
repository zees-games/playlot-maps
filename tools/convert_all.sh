#!/bin/bash
# Re-converts every imported map from its source BSP with the family's converter (dot-map-convert's playlot-maps
# adapter, through tools/import_bsp.py). Never hand-edit a converted document: change the converter or its tables.
#   tools/convert_all.sh [CONFIG_NAME...]      (no name = every row of tools/convert_sources.tsv)
# gm_construct_small has no row: its source BSP is in neither ~/projects/mapsrc nor ~/godot/inspirations, so
# pgc_construct_small.json stays as it is until the owner supplies the BSP.
# MAPSRC overrides the source root. Python runs with -P: the BSPs are downloads.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${MAPSRC:-$HOME/projects/mapsrc}"
[ -d "$SRC" ] || SRC=/home/gamedev/projects/mapsrc
WANT=("$@")
fail=0
while IFS=$'\t' read -r name rel; do
    case "$name" in ''|'#'*) continue ;; esac
    if [ ${#WANT[@]} -gt 0 ] && [[ ! " ${WANT[*]} " == *" $name "* ]]; then continue; fi
    bsp="$SRC/$rel"
    [ -f "$bsp" ] || { echo "convert_all: $name: missing source $bsp" >&2; fail=1; continue; }
    echo "== $name <- $rel"
    python3 -P "$HERE/tools/import_bsp.py" "$bsp" "$name" || { echo "convert_all: $name FAILED" >&2; fail=1; }
done < "$HERE/tools/convert_sources.tsv"
[ $fail -eq 0 ] || exit 1
# The importer does not write the ambience row; build_maps.py --ambient patches it in (a re-import drops it).
python3 -P "$HERE/tools/build_maps.py" --ambient
DOT_MAP_CONVERT_PATH="${DOT_MAP_CONVERT_PATH:-${DOTBSP_PATH:-$HERE/../dot-map-convert}}" python3 -P "$HERE/tools/build_provides.py"
