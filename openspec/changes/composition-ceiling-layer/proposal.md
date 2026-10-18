## Why

The owner wants to place a pendant lamp (Höffner "Pendelleuchte Calisto", 500 × 500 × 1100 mm including cable and ceiling canopy) from the model library in a room. Today every library model and stand-in stands on the floor, so the lamp would appear upside down, with its shade on the floor. It also cannot hang over a dining table, because the footprint check refuses any overlap with a standing item. The schema cannot say "this item hangs from the ceiling". In ladder terms this is a generator-extension request: the schema, its checks and the composition generator must grow.

## What Changes

- `layer` on a `stand-in` or `model` item accepts a second value, `"ceiling"`, beside `"floor"`. A ceiling-layer item hangs with its highest point at its room's ceiling. Its stated height is measured from the ceiling down to its lowest point, including the cable and canopy. Any other value is still refused by name, and a `piece` still does not take the field.
- Placement checks use each item's height range. A floor-layer or standing item reaches from the floor up to its height. A ceiling-layer item reaches from the ceiling down to its height. Footprint overlaps work as follows:
  - A ceiling-layer item may overlap another item when there is a vertical gap between them, for example a lamp over a table.
  - Two ceiling-layer items whose footprints overlap are refused.
  - Overlaps that do not involve a ceiling-layer item are checked as today.
- A ceiling-layer item blocks a door or window only when it hangs lower than the top of that opening. The configured placement rules (`front_clearance_mm`, `door_swing_clear`) do not apply to it. The room-outline, wall-end and ceiling-height checks still apply.
- The stored document keeps `layer: "ceiling"`. Its resolved item records `base_mm`, the height of the item's lowest point above the floor.
- The composition generator lifts a ceiling-layer stand-in or model so that its lowest point is at `base_mm`, which puts its top at the ceiling. The build report's `lowest_mm` states that height.
- The composition note shows "(ceiling layer)". The `compose_room` tool description and the Designer instructions tell the Designer to use the ceiling layer for pendant lamps and other items that hang from the ceiling.

No breaking change: documents without `layer`, or with `layer: "floor"`, are checked and built exactly as before, and stored versions are not rewritten.

Ladder step 2 (generator extension: schema, checks and composition generator). Agent touched: Designer (`compose_room`); the Builder renders the composition unchanged. Render guard: not affected; a composition still renders only through it. `bpy` allow-list: not affected; the change is in a checked-in headless generator, not a live script.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `room-composition`: the document's `layer` gains the value `"ceiling"`. Placement checks compare height ranges for ceiling-layer items, both for overlaps and for openings, and leave placement rules out for them. The headless build hangs ceiling-layer items with their top at the ceiling of their room.

## Impact

- `backend/app/blender/composition_contract.py`: accept `layer: "ceiling"`; compare height ranges in the overlap and opening checks; leave ceiling-layer items out of the rule subjects; record `base_mm` on the resolved item.
- `backend/app/blender/generators/_composition.py`: place a stand-in and a model at `base_mm` instead of z = 0.
- `backend/plugins/compose_room/tool.py`, `backend/app/agent/instructions/designer.md`, `backend/app/agent/prompts.py` (composition note): describe and show the value. `house_file.placed_items` already carries `layer`.
- Frontend: no change. The rooms page lists items by id, type and name, and the 3D room view shows the built `model.glb`.
- Tests: `backend/tests/test_composition_contract.py`, `test_compose_room.py`, `test_house_file.py`, and the `--blender` suite's `test_composition_blender.py`.
- No migration: compositions are stored as JSON documents, and both `layer` and `base_mm` are optional.
