#!/bin/bash
# Publishes the maps pack (licence.json and provides.json at the root travel with it) as playlot-maps: the id the client
# shell's solo.json and the server's content overrides mount for game-playlot. legacy id: playlot-maps was the pre-rename id
# (dev 1.1.0 only); nothing live mounts it, so a publish under it never reaches a player.
#   tools/publish.sh VERSION [extra publish_pack.sh flags, e.g. --site URL --token-file F --lock F --dry-run]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# publish_pack.sh --lock rewrites the lock to the site it published to (a dev origin). The lock ships inside the pack and the release gate
# (check-pack-static --deny tmcdev) rejects it: never commit that. Warn loudly when the lock now names a non-prod origin.
lock_guard() {
    local o; o=$(python3 -I -c 'import json,sys;print(json.load(open(sys.argv[1])).get("origin",""))' "$HERE/content.lock.json" 2>/dev/null || true)
    case $o in https://content.gamespice.net/*) ;; *) echo "publish: WARNING content.lock.json origin is now '$o', not the prod origin. Do NOT commit it: git checkout -- content.lock.json (the release gate rejects dev origins)." >&2 ;; esac
}
V=${1:?usage: tools/publish.sh VERSION [flags]}; shift
trap lock_guard EXIT
"$HERE/../gs-cloud/tools/publish_pack.sh" publish --source "$HERE" --id playlot-maps --version "$V" \
    --exclude-dir tools --exclude-dir docs --exclude-dir .github \
    --lock "$HERE/content.lock.json" "$@"
