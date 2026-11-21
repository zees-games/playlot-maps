#!/usr/bin/env python3
"""Writes provides.json, the Workshop listing; the logic is gs-map-convert's tools/build_provides.py.

    tools/build_provides.py            # rewrite
    tools/build_provides.py --check    # exit 1 if stale or an entry is bad

gs-map-convert is a sibling checkout (`../gs-map-convert`, where gs-bootstrap clones it) or `$GS_MAP_CONVERT_PATH`.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TITLE = 'Playlot maps'
GAMES = ["gamemann/game-playlot"]  # legacy id: the game's published pack id
DIR = 'maps'
DOC_KIND = None  # every .json in maps/ is a Playlot document: build_maps.py writes kind playlot_map, the converted ones
# (gs-map-convert's adapter) still the kind from before the rename, and the shared tool takes one kind only
MAP_KIND = lambda d: d["map_kind"]  # the entry's map_kind, or a callable taking the document


for _p in (os.environ.get("GS_MAP_CONVERT_PATH", ""), os.path.join(ROOT, "..", "gs-map-convert")):
    if _p and os.path.isfile(os.path.join(_p, "tools", "build_provides.py")):
        sys.path.insert(0, os.path.join(_p, "tools"))
        break
else:
    sys.exit("build_provides: gs-map-convert was not found. Clone it beside this repository or set GS_MAP_CONVERT_PATH.")
import build_provides  # noqa: E402

sys.exit(build_provides.run(ROOT, GAMES, title=TITLE, directory=DIR, doc_kind=DOC_KIND, map_kind=MAP_KIND))
