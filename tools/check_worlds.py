"""Every converted map (a document with a world pack) is the author's world, and a player starts on it.

For each maps/*.json that names a world pack:
  - the pack's .json and .bin are here, and the bin is the one the pack names (sha256);
  - nothing was cropped away: no `crop` in the document's world, no `crop:*` drops in the pack, and the hulls the
    converter left out (bar the 3D sky's, drawn elsewhere) are at most --max-absent percent of the map's;
  - the spawn is inside the world's bounds (its drawn surfaces, 3D sky left out), stands on a solid box of the
    document within --max-drop metres below it, and sees a drawn floor under it within the same reach.

A map that fails is named with the reason, and the exit status is 1. Nothing is capped: --max-absent and
--max-drop are thresholds, and a negative value turns that test off (loudly, in the output).

--published ORIGIN (e.g. https://dev.dotgames.org/content) also fetches each map's per-map pack
(<owner>/<id>, latest) and says where its document differs from this one (another sha, a crop, no world):
what a client mounts for ?map=<id>. Run by hand; CI does not reach the content origins.

  python3 -I tools/check_worlds.py [--max-absent 1] [--max-drop 2] [--published ORIGIN [--owner gamemann]] [MAP_ID...]
"""

import argparse
import array
import base64
import gzip
import hashlib
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MAPS = os.path.join(HERE, "..", "maps")
NOT_SOLID = {"water", "glass_see_through", "liquid"}


def _floats(raw, offset, count):
    a = array.array("f")
    a.frombytes(raw[offset:offset + 4 * count])
    if sys.byteorder != "little":
        a.byteswap()
    return a


def _uints(raw, offset, count):
    a = array.array("I")
    a.frombytes(raw[offset:offset + 4 * count])
    if sys.byteorder != "little":
        a.byteswap()
    return a


def world_floor(pack, raw, x, z, top):
    """The highest drawn triangle (3D sky left out) under (x, z) at or below `top`, in pack metres, or None."""
    best = None
    for s in pack["surfaces"]:
        if s.get("sky3d"):
            continue
        n = int(s["vertex_count"])
        pos = _floats(raw, int(s["position_offset"]), 3 * n)
        idx = _uints(raw, int(s["index_offset"]), int(s["index_count"]))
        for t in range(0, len(idx) - 2, 3):
            a, b, c = idx[t] * 3, idx[t + 1] * 3, idx[t + 2] * 3
            ax, az, bx, bz, cx, cz = pos[a], pos[a + 2], pos[b], pos[b + 2], pos[c], pos[c + 2]
            if x < min(ax, bx, cx) or x > max(ax, bx, cx) or z < min(az, bz, cz) or z > max(az, bz, cz):
                continue
            d = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
            if abs(d) < 1e-9:
                continue
            l1 = ((bz - cz) * (x - cx) + (cx - bx) * (z - cz)) / d
            l2 = ((cz - az) * (x - cx) + (ax - cx) * (z - cz)) / d
            l3 = 1.0 - l1 - l2
            if l1 < -1e-6 or l2 < -1e-6 or l3 < -1e-6:
                continue
            y = l1 * pos[a + 1] + l2 * pos[b + 1] + l3 * pos[c + 1]
            if y <= top and (best is None or y > best):
                best = y
    return best


def world_bounds(pack, raw):
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    for s in pack["surfaces"]:
        if s.get("sky3d"):
            continue
        pos = _floats(raw, int(s["position_offset"]), 3 * int(s["vertex_count"]))
        for k in range(3):
            col = pos[k::3]
            if col:
                lo[k] = min(lo[k], min(col))
                hi[k] = max(hi[k], max(col))
    return lo, hi


def _turned_top(b, x, z):
    """The highest point of the vertical line through (x, z) inside a box turned by `turn` (axis x, y, z, degrees)."""
    import math
    ax, ay, az, deg = (float(v) for v in b["turn"])
    n = math.sqrt(ax * ax + ay * ay + az * az) or 1.0
    ax, ay, az = ax / n, ay / n, az / n
    c, s_ = math.cos(math.radians(-deg)), math.sin(math.radians(-deg))
    def rot(v):     # Rodrigues, by -deg: world offset into the box's frame
        vx, vy, vz = v
        d = ax * vx + ay * vy + az * vz
        cx, cy, cz = ay * vz - az * vy, az * vx - ax * vz, ax * vy - ay * vx
        return [vx * c + cx * s_ + ax * d * (1 - c), vy * c + cy * s_ + ay * d * (1 - c), vz * c + cz * s_ + az * d * (1 - c)]
    o = rot([x - b["at"][0], -b["at"][1], z - b["at"][2]])      # the line at world y = 0
    u = rot([0.0, 1.0, 0.0])                                       # and its direction
    lo, hi = float("-inf"), float("inf")
    for k in range(3):
        h = float(b["size"][k]) / 2
        if abs(u[k]) < 1e-9:
            if abs(o[k]) > h:
                return None
            continue
        t0, t1 = (-h - o[k]) / u[k], (h - o[k]) / u[k]
        lo, hi = max(lo, min(t0, t1)), min(hi, max(t0, t1))
    return hi if lo <= hi else None


def box_floor(doc, x, z, top):
    """The highest top of a solid box of the document (turned ones too) under (x, z) at or below `top`, or None."""
    best = None
    for b in doc.get("boxes", []):
        if str(b.get("material", "")) in NOT_SOLID:
            continue
        (cx, cy, cz), (sx, sy, sz) = b["at"], b["size"]
        if b.get("turn"):
            r = max(sx, sy, sz)
            if abs(x - cx) > r or abs(z - cz) > r:
                continue
            y = _turned_top(b, x, z)
            if y is None:
                continue
        else:
            if abs(x - cx) > sx / 2 or abs(z - cz) > sz / 2:
                continue
            y = cy + sy / 2
        if y <= top and (best is None or y > best):
            best = y
    return best


def absent_hulls(pack):
    """(hulls left out, hulls in the source) bar the 3D sky's."""
    gone = sum(int(v) for k, v in (pack.get("skipped") or {}).items()
               if k.startswith("crop:hull") or (k.startswith("hull:") and k != "hull:sky3d"))
    return gone, int(pack["counts"]["hulls"]) + gone


def check(path, max_absent, max_drop):
    """Problems with one document, [] when it is right, None when it has no world pack (a hand-built map)."""
    doc = json.load(open(path))
    w = doc.get("world")
    if not isinstance(w, dict):
        return None
    probs = []
    base = os.path.join(os.path.dirname(path), "world", w["pack"])
    pj = os.path.join(base, os.path.basename(path))
    if not os.path.exists(pj):
        return ["world pack %s missing" % os.path.relpath(pj, MAPS)]
    pack = json.load(open(pj))
    bp = os.path.join(base, pack["bin"]["file"])
    if not os.path.exists(bp):
        return ["world bin %s missing" % os.path.relpath(bp, MAPS)]
    stored = open(bp, "rb").read()
    raw = gzip.decompress(stored) if pack["bin"].get("compression") == "gzip" else stored
    if pack["bin"]["sha256"] not in (hashlib.sha256(stored).hexdigest(), hashlib.sha256(raw).hexdigest()):
        probs.append("world bin sha256 is not the pack's")
    if w.get("crop"):
        probs.append("world is cropped to %s (re-convert the whole map)" % w["crop"])
    crops = {k: v for k, v in (pack.get("skipped") or {}).items() if k.startswith("crop:")}
    if crops:
        probs.append("world pack dropped %s by a crop" % crops)
    gone, total = absent_hulls(pack)
    pct = 100.0 * gone / total if total else 0.0
    if max_absent >= 0 and pct > max_absent:
        probs.append("%.1f%% of the source's hulls absent (%d of %d), over %.1f%%" % (pct, gone, total, max_absent))
    off = w.get("offset") or [0.0, 0.0, 0.0]
    sx, sy, sz = (float(v) for v in doc["spawn"])
    lo, hi = world_bounds(pack, raw)
    px, py, pz = sx - off[0], sy - off[1], sz - off[2]
    at = [round(v, 2) for v in (sx, sy, sz)]
    if not (lo[0] <= px <= hi[0] and lo[2] <= pz <= hi[2] and lo[1] - 1.0 <= py <= hi[1] + 1.0):
        probs.append("spawn %s is outside the world's bounds %s..%s" % (
            at, [round(v + o, 1) for v, o in zip(lo, off)], [round(v + o, 1) for v, o in zip(hi, off)]))
    if max_drop >= 0:
        solid = box_floor(doc, sx, sz, sy + 0.05)
        if solid is None or sy - solid > max_drop:
            probs.append("spawn %s has no solid box under it within %.1f m (nearest top %s)" % (
                at, max_drop, None if solid is None else round(solid, 2)))
        drawn = world_floor(pack, raw, px, pz, py + 0.05)
        if drawn is None or py - drawn > max_drop:
            probs.append("spawn %s sees no drawn floor under it within %.1f m (nearest %s)" % (
                at, max_drop, None if drawn is None else round(drawn + off[1], 2)))
    return probs


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "playlot-maps check_worlds"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def published(origin, owner, mid, path):
    """How the per-map pack <owner>/<mid> at its latest version differs from this repository's document."""
    base = "%s/%s/%s/" % (origin.rstrip("/"), owner, mid)
    try:
        ver = json.loads(_get(base + "latest.json")).get("version")
        p = json.loads(_get("%s%s/manifest.json" % (base, ver)))["payload"]
    except Exception as e:      # noqa: BLE001 - a missing pack is the answer, reported
        return ["no published per-map pack %s/%s (%s)" % (owner, mid, e)]
    files = {f["path"]: f["sha256"] for f in json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))["files"]}
    rel = "maps/" + os.path.basename(path)
    here = json.load(open(path))
    out = []
    h = files.get(rel)
    if h is None:
        return ["%s@%s carries no %s" % (mid, ver, rel)]
    if h != _sha(path):
        doc = json.loads(_get("%s%s/objects/%s/%s" % (base, ver, h[:2], h)))
        w = doc.get("world") or {}
        why = ["no world pack"] if not w else []
        if w.get("crop"):
            why.append("cropped to %s" % w["crop"])
        why.append("%d boxes, here %d" % (len(doc.get("boxes", [])), len(here.get("boxes", []))))
        out.append("%s@%s document is not this one: %s" % (mid, ver, "; ".join(why)))
    mw = (here.get("world") or {}).get("pack")
    if mw:
        wanted = "maps/world/%s/%s" % (mw, os.path.basename(path))
        if wanted not in files:
            out.append("%s@%s carries no world pack %s" % (mid, ver, mw))
        elif files[wanted] != _sha(os.path.join(MAPS, "world", mw, os.path.basename(path))):
            out.append("%s@%s world pack %s is not this one" % (mid, ver, mw))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--max-absent", type=float, default=1.0, help="percent of the source's hulls a world may leave out (negative: off)")
    ap.add_argument("--max-drop", type=float, default=2.0, help="metres from the spawn down to its floor (negative: off)")
    ap.add_argument("--published", metavar="ORIGIN", help="also compare each map's published per-map pack with this repository")
    ap.add_argument("--owner", default="gamemann")
    ap.add_argument("ids", nargs="*")
    a = ap.parse_args(argv)
    if a.max_absent < 0:
        print("check_worlds: absent-hull test OFF (--max-absent %s)" % a.max_absent)
    if a.max_drop < 0:
        print("check_worlds: spawn support test OFF (--max-drop %s)" % a.max_drop)
    bad = seen = 0
    for name in sorted(os.listdir(MAPS)):
        mid = name[:-5]
        if not name.endswith(".json") or (a.ids and mid not in a.ids):
            continue
        path = os.path.join(MAPS, name)
        probs = check(path, a.max_absent, a.max_drop)
        if probs is None:
            continue
        seen += 1
        if a.published:
            probs = probs + published(a.published, a.owner, mid, path)
        for p in probs:
            print("%s: %s" % (mid, p))
        bad += bool(probs)
    if a.ids and seen == 0:
        print("check_worlds: none of %s is a converted map here" % a.ids, file=sys.stderr)
        return 2
    print("check_worlds: %d converted maps, %d with problems" % (seen, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
