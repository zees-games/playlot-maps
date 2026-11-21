#!/bin/bash
# Publishes the PBR sets and library models the converted worlds draw as gs-cloud slices (VRAM-compressed, cut by the group
# of maps that draw them) and stamps each world manifest (maps/world/<pack>/<id>.json) with licence.store_pack. Without it a
# web client, which has no maps/world/.stores, draws every library model as a box or a lollipop tree and every PBR set as
# its 64 px fallback. Copied from zombie-zone-maps (separate repositories: the family's rule).
#   [SHIP_IDS="pgc_fork ..."] [GODOT=bin] [DIST=dir] [STORE_PROJECT=dir] [STORE_SITE=url STORE_TOKEN_FILE=f [STORE_ORIGIN=url]] tools/ship_store.sh
# Run it on a box with memory and the engine: `../gpu.sh py --stage ../gs-cloud -- bash tools/ship_store.sh` (see
# docs/building.md#store-slices). With STORE_SITE the slices the stamps name (and their dependencies) are uploaded through
# that site's pack API (tools/upload_store.py; slice versions are h-hashes, which publish_pack.sh refuses), skipping what
# STORE_ORIGIN already serves. Dev: STORE_SITE=https://tmcdev.net STORE_ORIGIN=https://dev.dotgames.org with a dev
# creator token; prod: the production site with gamemann's prod creator token (the owner's). The site signs each manifest.
# A version the site once FAILED is never taken again: list it in tools/store_burnt.txt and the slice moves to a new version.
# Then publish the packs (tools/publish_maps.sh adds --depends <store_pack>; GSMapStore.ensure fetches it otherwise).
set -o pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
BSP="${GS_BSP_PATH:-${GSBSP_PATH:-$HERE/../../gs-map-convert}}"
CLOUD="${GS_CLOUD:-$HERE/../../gs-cloud}"
OUT="${STORE_PROJECT:-$HERE/../.stores/project}"
DIST="${DIST:-$HERE/../.stores/dist}"
packs=()
while IFS=$'\t' read -r id manifest; do packs+=("$manifest"); done < <(python3 -I "$HERE/store_worlds.py" ${SHIP_IDS:-}) || exit
[ ${#packs[@]} -gt 0 ] || { echo "ship_store: no world manifests" >&2; exit 2; }
touch "$HERE/store_burnt.txt"
python3 -P "$BSP/bsp.py" storepack "${packs[@]}" --out "$OUT" --dist "$DIST" --cloud "$CLOUD" --burnt "$HERE/store_burnt.txt" \
    ${GODOT:+--godot "$GODOT"} ${STORE_SHARED:+--shared "$STORE_SHARED"} ${STORE_KEY:+--key "$STORE_KEY"} || exit
[ -n "${STORE_SITE:-}" ] || exit 0
[ -s "${STORE_TOKEN_FILE:-}" ] || { echo "ship_store: STORE_SITE needs STORE_TOKEN_FILE (a creator token of the slice owner)" >&2; exit 2; }
exec python3 -P "$HERE/upload_store.py" "${packs[@]}" --site "$STORE_SITE" --token-file "$STORE_TOKEN_FILE" --project "$OUT" \
    --dist "$DIST" --bsp "$BSP" --cloud "$CLOUD" ${STORE_ORIGIN:+--origin "$STORE_ORIGIN"}
