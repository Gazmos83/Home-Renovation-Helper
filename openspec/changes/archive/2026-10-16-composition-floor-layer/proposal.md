## Why

The owner asked for a rug under the grey sofa in Wohnen and the composition check refused it: `items grey-sofa (wall 4, offset 0 mm) and rug (free at x 2066, y 4430 mm, rotated 168°) overlap`. Every footprint overlap is refused today, so a rug, runner or mat lying under furniture cannot be expressed. In ladder terms this is a generator-extension request: the schema cannot say "this item lies flat on the floor", so the schema and its checks grow.

## What Changes

- A `stand-in` or `model` item in a room composition may carry an optional `layer` field. Its only allowed value is `"floor"`; any other value is refused by name. A `piece` item does not take the field.
- A floor-layer item must be at most 30 mm tall; a taller one is refused, naming the item and the limit.
- A floor-layer item may overlap standing items (no `layer`). Two floor-layer items that overlap are still refused, and so are two standing items, as today.
- The door and window opening checks and the configured placement rules (`front_clearance_mm`, `door_swing_clear`) do not apply to a floor-layer item: a flat rug does not block a doorway. The room outline, wall-end and ceiling checks still apply.
- The stored composition keeps `layer`, the composition note shows it, and the `compose_room` tool description and the Designer instructions tell the Designer to use it for rugs and mats.
- The generator is unchanged: a floor-layer stand-in is the same box at floor level, only thin, and a model is scaled to its stated size as today.

No breaking change: documents without `layer` behave exactly as before.

Ladder step 2 (generator extension: schema and checks). Agent touched: Designer (`compose_room`). Render guard: not affected; the composition still renders only through it. `bpy` allow-list: not affected; no live script changes.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `room-composition`: the document gains an optional floor `layer` on stand-ins and models, and the placement requirement exempts floor-layer items from the overlap check against standing items and from the opening checks and placement rules.

## Impact

- `backend/app/blender/composition_contract.py`: parse `layer`, cap the height, skip the overlap check between a floor-layer and a standing item, skip the opening check for floor-layer items, and leave floor-layer items out of the rule subjects so placement rules skip them.
- `backend/plugins/compose_room/tool.py`, `backend/app/agent/instructions/designer.md`, `backend/app/agent/prompts.py` (composition note): describe and show the field.
- Frontend: no change. The rooms page lists items by id, type and name, which stays enough.
- Tests: `backend/tests/test_composition_contract.py`, `test_compose_room.py`, `test_prompts`-style coverage for the note.
- No migration: compositions are stored as JSON documents, and `layer` is optional.
