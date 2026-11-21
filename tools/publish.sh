#!/bin/bash
# Publishes the maps pack (licence.json and provides.json at the root travel with it) as playlot-maps: the id the client
# shell's solo.json and the server's content overrides mount for game-playlot. legacy id: playlot-maps was the pre-rename id
# (dev 1.1.0 only); nothing live mounts it, so a publish under it never reaches a player.
#   tools/publish.sh VERSION [extra publish_pack.sh flags, e.g. --site URL --token-file F --lock F --dry-run]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
V=${1:?usage: tools/publish.sh VERSION [flags]}; shift
exec "$HERE/../gs-cloud/tools/publish_pack.sh" publish --source "$HERE" --id playlot-maps --version "$V" \
    --exclude-dir tools --exclude-dir docs --exclude-dir .github \
    --lock "$HERE/content.lock.json" "$@"
