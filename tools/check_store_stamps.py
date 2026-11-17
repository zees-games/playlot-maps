"""Every converted world that draws library models or PBR sets names the dot-cloud slice that holds them
(licence.store_pack, stamped by tools/ship_store.sh). Without the stamp a web client, which never gets maps/world/.stores
(a hidden folder, never published), draws each library model as a box or a lollipop tree and each PBR set as its 64 px
fallback, and tools/publish_maps.sh has no --depends to give the map's pack.
  python3 -I tools/check_store_stamps.py [MAP_ID ...]
Exit 1 with one line per unstamped or malformed world. Run in CI (.github/workflows/check.yml).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store_worlds  # noqa: E402

SLICE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}/[a-z0-9][a-z0-9_.-]{0,127}$")


def _ref_errors(ref, where):
    if not isinstance(ref, dict):
        return ["%s is not an object" % where]
    errs = []
    if not SLICE_ID.match(str(ref.get("id", ""))):
        errs.append("%s.id %r is not an owner/name slice id" % (where, ref.get("id")))
    if not str(ref.get("version", "")).strip():
        errs.append("%s has no version" % where)
    return errs


def check(ids=()):
    errs = []
    for mid, path in store_worlds.worlds(ids):
        rel = os.path.relpath(path, store_worlds.ROOT)
        if not os.path.isfile(path):
            errs.append("%s: %s is missing" % (mid, rel))
            continue
        with open(path, encoding="utf-8") as f:
            lic = json.load(f).get("licence") or {}
        if not (lic.get("model_stand_ins") or lic.get("textures")):
            continue  # draws nothing from the stores
        sp = lic.get("store_pack")
        if sp is None:
            errs.append("%s: %s has no licence.store_pack (run SHIP_IDS=%s tools/ship_store.sh)" % (mid, rel, mid))
            continue
        errs += ["%s: %s" % (mid, e) for e in _ref_errors(sp, "store_pack")]
        shared = sp.get("shared", []) if isinstance(sp, dict) else []
        if not isinstance(shared, list):
            errs.append("%s: store_pack.shared is not a list" % mid)
            continue
        for i, ref in enumerate(shared):
            errs += ["%s: %s" % (mid, e) for e in _ref_errors(ref, "store_pack.shared[%d]" % i)]
    return errs


if __name__ == "__main__":
    problems = check(sys.argv[1:])
    for p in problems:
        print(p, file=sys.stderr)
    if problems:
        sys.exit(1)
    print("check_store_stamps: %d worlds stamped" % len(store_worlds.worlds(sys.argv[1:])))
