# Building a map

How a document is written, what its boxes may be made of, what it may carry, and how it reaches a player. The format itself is game-playlot's: [maps.md](../../game-playground/docs/maps.md#custom-maps-are-documents).

## Why documents and not map scripts

The built-in maps are `_build()` scripts. A map delivered in a pack of its own is mounted at another prefix than the game, and a script there that `extends` the game's map base by path names a path that is only right in one of the two places it runs (the family's mount constraint). Boxes are data: either pack can be anywhere.

## How the game reads them

`maps/` is linked into game-playlot by dot-bootstrap (`game-playground/.gitignore`: `# bootstrap-link: game-playground-maps/maps` → `/maps/custom`). `Playground.map_catalogue()` adds every `.json` there as a `DotMapDef` built by the shared `res://maps/pg_data.tscn`, with the document's path in `meta.doc`; a document that does not read is left out with a WARN, and an id the catalogue already has is never replaced.

## The builder

`tools/build_maps.py` writes every document, and the JSON is committed. Edit the builder, run it, commit both; `--check` fails when a committed file differs (CI runs it).

- **Ramps are placed by their top surface's two ends** (`ramp_z`, `ramp_x`, `bridge()`) and dropped along their normal by half their thickness, so the surface meets the ground exactly at both ends. Dropped vertically, the top end is a lip, and over a step's height a lip is a wall.
- `slab_with_holes()` cuts ponds and pits into a ground. A hole needs a ground thick enough to give it sides.
- `pit_steps()` climbs out of a hole by 0.4 m steps the width of the hole, wall to wall, so a step's side faces nothing. A ramp down into a pit leaves an enclosed wedge under it, which the survey reports.
- `building(..., windows=, rows=)` and `wall_run()` cut window openings and fill them with glass the wall's whole thickness: a thinner pane leaves a recess a 0.25 m survey column can read as a gap. Windows stay 3 m either side of a doorway so its buttons stay on wall.
- `mat(material, at, size)`, or `box(..., colour, material=...)` to keep a colour; `trampoline()`, `bush()`.

## Materials

A box may name a `material`: one of dot-physics' standard surfaces, drawn in its own look unless it names a colour (a see-through material keeps its transparency in a mapper's colour). Every map uses them. How each behaves is game-playlot's: [Map materials](../../game-playground/docs/maps.md#map-materials).

- Water, slime and lava are liquid volumes and foliage is a volume, none with a collider. Glass and thin ice are panes that break.
- **A movement surface is part of a measured route.** Concrete, metal, wood and rock have no drag and move a player exactly as a box with no material did; grass, dirt, sand and snow slow a run (0.955, 0.94, 0.82, 0.88 of top speed). Nothing a jump was measured on may be given one of the slow ones.
- **A see-through material shows what is inside it.** Overlapping slabs under ice show through ([history](history.md#what-the-render-found)).

## Props and wires

A document may list `props` (catalogue ids, frozen unless `loose`) and `wires` between them, which game-playlot puts down on the server when the map loads ([Map props](../../game-playground/docs/maps.md#map-props)). `prop()` takes the floor a prop stands on and adds half its height from `HALF_HEIGHT`; **keep that table in step with game-playlot's catalogue**.

**Never put a loose prop under water.** game-playlot's buoyancy (`_float_props`) launches a prop put down on a bed: a beach ball on the harbour's bed went two kilometres up. A prop is placed floating at its own waterline; game-playlot's `tools/map_props.gd` loads every map and finds one that is not.

## Toys

Each map's `toys` are dot-props' toy placements (`{toy, at, yaw, links?}`), which game-playlot builds on both ends in the document's order; a switch's `links` are indices into that list. The builder's `TOYS` table says roughly where each map wants each toy (`toy(id, x, z, y)`, themed per map), and `settle` moves it to the nearest spot within 14 m that is floored flat under its whole footprint (never on water, lava, slime, foliage or thin ice), half a metre clear of every solid box, prop and toy already placed, with five metres of air over a trampoline or pad and a pad's flight clear. `exact=True` keeps a set laid out together where it is (`pins()`, a rack of six). A hint that settles nowhere stops the build rather than leaving a toy out, because a later switch would then name the wrong lamps. game-playlot's `headless_playground` (`_test_every_maps_toys_stand_clear`) loads every map and checks each toy is built, inside nothing, and still where it was put two seconds later.

## Checking a map

- game-playlot's `headless_playground` surveys every map ([Every hand-built map is surveyed](../../game-playground/docs/maps.md#every-hand-built-map-is-surveyed)): no slot, nothing unreached but what the document declares (crane jibs, shelves, container tops, lake beds), no trap.
- The survey reads a tilted box as its world AABB, so it can report slots between tilted boxes that are not there ([history](history.md#the-bowls-sixteen-slots-that-were-not-there)). Widen the boxes rather than accept a failure.
- game-playlot's `dedicated` loads them through the catalogue (`map pgc_quarry`).
- `game-playground/tools/screenshot.sh <map>` renders one, with an angle on each map's material set pieces. Look at it: colours that vanish into a floor and things showing through ice were found only by a picture.

## Delivery

A client builds the map too, so this is a **`dependencies`** pack, not `server_dependencies`: every client fetches it in the same content sync as the game. Both ends then add `<mount prefix>/maps`: the server from the game manager's dependency keys (`PlaygroundModule._add_delivered_maps`), the client from `DotClientLink.content_extra` (`PlaygroundClient`). dot-server-deploy has `content/playground_maps/pack.json` (`tmc/playground_maps`, excluding `tools` and `.github`) and `content/playground/game.yml` names it under `dependencies`. The release workflow builds the pack from a `v*` tag.

## Store slices

A converted world (`maps/world/<pack>/<id>.json`) draws library models and PBR sets that live in `maps/world/.stores/` (`licence.model_store`, `licence.pbr_store`). That folder is hidden, so no pack ever carries it: a web client drew every library model as a box or a lollipop tree and every PBR set as its 64 px fallback (nightly `playlot-store-slices`, 2026-11-16). The art ships the way zombie-zone-maps ships it, as dot-cloud **store slices**:

- `tools/ship_store.sh` runs dot-map-convert's `bsp.py storepack` over every world `tools/store_worlds.py` lists (`SHIP_IDS="pgc_fork ..."` for some): it builds the slices (VRAM-compressed, maps that draw the same items share a `store-shared-<hash>` slice), publishes them into `.stores/dist` and stamps each manifest with `licence.store_pack` (`{id, version, shared}`). It needs the engine and memory: `../gpu.sh py --stage ../dot-cloud -- bash tools/ship_store.sh`. Commit the stamped manifests.
- With `STORE_SITE` and `STORE_TOKEN_FILE` (a creator token of gamemann) it then uploads the slices dependencies first (`tools/upload_store.py`), skipping what `STORE_ORIGIN` already serves. Dev: `STORE_SITE=https://tmcdev.net STORE_ORIGIN=https://dev.dotgames.org`. The production upload is the owner's.
- `tools/check_store.sh` (`DIST=dir`, or `ORIGIN=url`) checks every stamped slice is published and complete; `tools/check_store_stamps.py` (CI) fails on a world with art and no stamp.
- `tools/publish_maps.sh` gives each map pack `--depends <store_pack id@version>`, so the platform mounts the slices with the map; for the whole `playlot-maps` pack (fourteen worlds) the game's `DotMapStore.ensure` (dot-map, through `pg_data.load_world`) fetches each world's slice when it loads.
- A slice version the site once FAILED is never taken again: add `id@version` to `tools/store_burnt.txt` and run `ship_store.sh` again.
- Check a delivery from frames: in game-playlot, `tools/screenshot.sh <map> --doc <a copy without .stores> --cloud-store <origin>/content,<pubkey>`.

