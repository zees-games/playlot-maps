#!/bin/bash
# Every world's art resolves from published slices: the stamp, each slice (and its dependencies) and every PBR set and model
# the manifest draws. Reads the signed slice manifests of .stores/dist (after ship_store.sh) or, with ORIGIN, the published
# ones, which is what a player's client reads (dev: ORIGIN=https://dev.dotgames.org).
#   [ORIGIN=url] [DIST=dir] tools/check_store.sh [map id ...]
HERE="$(cd "$(dirname "$0")" && pwd)"
BSP="${GS_BSP_PATH:-${GSBSP_PATH:-$HERE/../../gs-map-convert}}"
packs=()
while IFS=$'\t' read -r id manifest; do packs+=("$manifest"); done < <(python3 -I "$HERE/store_worlds.py" "$@") || exit
where=(--dist "${DIST:-$HERE/../.stores/dist}"); [ -n "${ORIGIN:-}" ] && { o="${ORIGIN%/}"; where=(--origin "${o%/content}"); }
exec python3 -P "$BSP/bsp.py" storecheck "${packs[@]}" "${where[@]}"
