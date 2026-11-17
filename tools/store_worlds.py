"""The converted worlds whose art ships as store slices: one line `<map id>\t<world manifest>` per maps/<id>.json that
names a world pack (maps/world/<pack>/<id>.json), sorted by map id. ship_store.sh, check_store.sh and
check_store_stamps.py read the list from here, so a newly converted map is covered without another table.
  python3 -I tools/store_worlds.py [MAP_ID ...]     (no id: every map with a world)
"""
import json
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def worlds(ids=()):
    out = []
    maps = os.path.join(ROOT, "maps")
    for name in sorted(os.listdir(maps)):
        if not name.endswith(".json"):
            continue
        mid = name[:-5]
        if ids and mid not in ids:
            continue
        with open(os.path.join(maps, name), encoding="utf-8") as f:
            w = json.load(f).get("world")
        pack = w.get("pack") if isinstance(w, dict) else w
        if not pack:
            continue
        out.append((mid, os.path.join(maps, "world", pack, mid + ".json")))
    missing = sorted(set(ids) - {m for m, _ in out})
    if missing:
        sys.exit("store_worlds: no world pack for %s" % ", ".join(missing))
    return out


if __name__ == "__main__":
    for mid, path in worlds(sys.argv[1:]):
        if not os.path.isfile(path):
            sys.exit("store_worlds: %s names %s, which is missing" % (mid, os.path.relpath(path, ROOT)))
        print("%s\t%s" % (mid, path))
