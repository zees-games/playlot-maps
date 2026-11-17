#!/bin/bash
# Publishes each map as its own pack (id = the map id, a member of this repository's collection asset): the pack a
# hotspot "Play map" link (`--solo-map <id>`) mounts instead of the whole game-playground-maps. tools/publish.sh still publishes the whole pack.
#   tools/publish_maps.sh [MAP_ID...] -- --member-of ASSET [--site URL --token-file F --dry-run ...]
# No MAP_ID = every maps/*.json. A pack holds maps/<id>.json, the world pack it names (maps/world/<pack>/, its meshes,
# textures and credits, and the library models its props use from maps/world/.stores/), its licence.json entries and a
# one-entry provides.json.
# --member-of is required: a bare publish of a map pack creates a Workshop page of its own. The first publish of a map is
# 1.0.0, later ones --bump patch; maps.lock.json pins them (content.lock.json stays the whole pack's, which bootstrap fetches).
# A converted world's pack names the dot-cloud slice that holds its library models and PBR sets (licence.store_pack, which
# tools/ship_store.sh stamps and uploads) with --depends id@version, so a web client, which has no maps/world/.stores (a
# hidden folder, never published), gets the real models and textures, not boxes and 64 px fallbacks. An unstamped world
# stops the publish: run tools/ship_store.sh first.
# GS_CLOUD overrides the dot-cloud checkout (default: the sibling ../dot-cloud).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IDS=(); while [ $# -gt 0 ] && [ "$1" != "--" ]; do IDS+=("$1"); shift; done
[ $# -gt 0 ] && shift
FLAGS=("$@")
[[ " ${FLAGS[*]} " == *" --member-of "* ]] || { echo "publish_maps.sh: --member-of ASSET is required (this repository's collection asset)" >&2; exit 2; }
[ ${#IDS[@]} -gt 0 ] || mapfile -t IDS < <(cd "$HERE/maps" && ls *.json | sed 's/\.json$//')
LOCK="$HERE/maps.lock.json"
STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT
for id in "${IDS[@]}"; do
    [[ "$id" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "not a map id: $id" >&2; exit 2; }
    rm -rf "${STAGE:?}/$id"; mkdir -p "$STAGE/$id/maps"
    python3 -I - "$HERE" "$id" "$STAGE/$id" <<'PY'
import json, os, shutil, sys
repo, mid, out = sys.argv[1:4]
rel = "maps/%s.json" % mid
with open(os.path.join(repo, "provides.json"), encoding="utf-8") as f:
    provides = json.load(f)
entries = [e for e in provides["entries"] if e.get("id") == mid and e.get("scene") == rel]
if len(entries) != 1:
    sys.exit("%s: provides.json has %d entries for it (run tools/build_provides.py)" % (mid, len(entries)))
provides["entries"] = entries
provides["title"] = entries[0].get("name", mid)
with open(os.path.join(repo, "licence.json"), encoding="utf-8") as f:
    licence = json.load(f)
mine = [dict(e, paths=[p for p in e["paths"] if p == rel]) for e in licence if rel in e.get("paths", [])]
root = [e for e in licence if "" in e.get("paths", [])]
shutil.copy(os.path.join(repo, rel), os.path.join(out, rel))
with open(os.path.join(repo, rel), encoding="utf-8") as f:
    world = (json.load(f).get("world") or {}).get("pack")
if world:
    # the converted world pack the map is drawn from: maps/world/<pack>/ beside the map document (DotMapDrawnWorld)
    if not isinstance(world, str) or "/" in world or world.startswith("."):
        sys.exit("%s: world pack %r is not a folder name" % (mid, world))
    src = os.path.join(repo, "maps", "world", world)
    if not os.path.isdir(src):
        sys.exit("%s: world pack maps/world/%s is missing (run tools/convert_all.sh %s)" % (mid, world, mid))
    shutil.copytree(src, os.path.join(out, "maps", "world", world))
    # the library models its props are drawn as: each row's store_file under the licence's model_store, and the files
    # a .glb names outside itself (a kit's shared Textures/colormap.png)
    with open(os.path.join(src, mid + ".json"), encoding="utf-8") as f:
        lic = json.load(f).get("licence") or {}
    store = os.path.normpath(os.path.join("maps", "world", world, lic.get("model_store", "model-library")))
    if not store.startswith(os.path.join("maps", "world") + os.sep):
        sys.exit("%s: model_store %r is outside maps/world" % (mid, lic.get("model_store")))
    want = set()
    for row in lic.get("model_stand_ins", []):
        sf = row.get("store_file")
        if not sf:
            continue
        rel_glb = os.path.normpath(os.path.join(store, sf))
        if not rel_glb.startswith(store + os.sep) or not os.path.isfile(os.path.join(repo, rel_glb)):
            sys.exit("%s: stand-in %s: %s is missing" % (mid, row.get("stand_in"), rel_glb))
        want.add(rel_glb)
        with open(os.path.join(repo, rel_glb), "rb") as g:
            head = g.read(20)
            if head[:4] == b"glTF":
                gltf = json.loads(g.read(int.from_bytes(head[12:16], "little")))
                for e in gltf.get("images", []) + gltf.get("buffers", []):
                    uri = e.get("uri", "")
                    if uri and not uri.startswith("data:"):
                        dep = os.path.normpath(os.path.join(os.path.dirname(rel_glb), uri.replace("%20", " ")))
                        if os.path.isfile(os.path.join(repo, dep)):
                            want.add(dep)
    for rel_file in sorted(want):
        os.makedirs(os.path.dirname(os.path.join(out, rel_file)), exist_ok=True)
        shutil.copy(os.path.join(repo, rel_file), os.path.join(out, rel_file))
    sp = lic.get("store_pack")
    if not (isinstance(sp, dict) and sp.get("id") and sp.get("version")):
        sys.exit("%s: maps/world/%s/%s.json has no licence.store_pack (run SHIP_IDS=%s tools/ship_store.sh)" % (mid, world, mid, mid))
    with open(os.path.join(out, ".depends"), "w", encoding="utf-8") as f:
        f.write("%s@%s\n" % (sp["id"], sp["version"]))
for name, doc in (("provides.json", provides), ("licence.json", root + mine)):
    with open(os.path.join(out, name), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=4)
        f.write("\n")
PY
    DEPS=()
    if [ -f "$STAGE/$id/.depends" ]; then DEPS=(--depends "$(cat "$STAGE/$id/.depends")"); rm -f "$STAGE/$id/.depends"; fi
    VER=(--version 1.0.0)
    [ -f "$LOCK" ] && grep -q "\"gamemann/$id\"" "$LOCK" && VER=(--bump patch)
    # The site allows a few claims a minute: on 429 wait and try again (nothing was claimed).
    for try in 1 2 3 4 5 6; do
        rc=0; out="$("${GS_CLOUD:-${DOT_CLOUD:-$HERE/../dot-cloud}}/tools/publish_pack.sh" publish --source "$STAGE/$id" --id "$id" "${VER[@]}" \
            --no-import --lock "$LOCK" "${DEPS[@]}" "${FLAGS[@]}" 2>&1)" || rc=$?
        printf '%s\n' "$out"
        [ $rc -ne 0 ] && grep -q rate_limited <<<"$out" && [ $try -lt 6 ] && { sleep 40; continue; }
        [ $rc -eq 0 ] || exit $rc
        break
    done
done
