## Why

In the end-to-end review of 2026-10-15 the owner asked that pieces and library models can be made invisible in a room design. Today the 3D room view has one "items" switch for all furniture together, so a single sofa cannot be hidden to see the wall behind it. A room version also cannot keep an item in its layout while leaving it out of the build and the renders. The owner chose both on 2026-10-18: a quick viewer switch per item, and a saved hidden flag for builds and renders. The schema cannot say "this item is hidden", so the saved half is a generator-extension request (ladder step 2).

## What Changes

- **A switch per item in the 3D room view.** The build report lists, for each placed item, its name and the mesh names it holds in `model.glb`. The room view replaces its single "items" switch with one switch per item, labelled with the item's name, plus "All items". Switching one off hides only that item's meshes. Nothing is saved: no new version, no rebuild, and the switches start on again when the view is reopened. Versions built before this change keep the single "items" switch.
- **A saved `hidden` flag.** Any item type (`piece`, `stand-in`, `model`) MAY carry `hidden: true` in the composition document. It goes through `compose_room`'s confirmation like any other change and makes a new room version. A hidden item:
  - stays in the document, the Rooms page's item list (marked "hidden") and the composition note;
  - is still checked for its shape: inside the room outline, not past the end of its wall, not taller than the ceiling, and a piece still has to be approved;
  - is left out of the overlap and opening checks and of the placement rules, so it never blocks another item. TODO(user): confirm that a hidden item should not block anything;
  - is not built, so it is absent from `model.blend`, `model.glb`, the screenshot, every render (draft or final), restyle variants and the detail pass's copy.
- `hidden: false` is accepted and stored as if the field were absent. Any other value is refused naming the item and `hidden`.
- The change list against the previous version says "hidden: <id>" or "shown: <id>" when only the flag changed.
- The Designer's tool description and instructions say how to hide an item and show it again. The composition note marks a hidden item "(hidden)".

No breaking change: documents without `hidden` are checked and built as before, and stored versions are not rewritten. Old build reports without per-item mesh lists keep the single "items" switch.

Depends on `composition-ceiling-layer`, which is in progress in the working tree and must be archived first. This change builds on its `layer` values and `base_mm`.

Ladder step 2 (generator extension: schema, checks and composition generator). Agents touched: the **Designer** (`compose_room` tool text and instructions); the Builder renders a composition unchanged. The **render guard** is **not affected**: a composition still renders only through it, and a hidden item simply is not in the scene. The **bpy allow-list** is **not affected**: the change is in a checked-in headless generator, not a live script.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `room-composition`: the document accepts `hidden` on every item type; hidden items are exempt from the overlap, opening and placement-rule checks but keep their shape checks; the headless build leaves hidden items out and the build report lists each built item's name and meshes.
- `studio-ui`: the Measured Rooms page's 3D view (and so the Workspace room pane, which uses the same view) offers one switch per item plus "All items", and the item list marks hidden items.

## Impact

- `backend/app/blender/composition_contract.py`: `hidden` in `_parse_item` (all types); `place_items` skips hidden items in the overlap, opening and rule-subject steps and records `hidden: true` on the resolved item.
- `backend/app/blender/generators/_composition.py`: `build_scene` skips hidden items, lists them in the report with `hidden: true`, and records `name` and `meshes` for each built item.
- `backend/app/blender/verify.py`: each report item's `meshes` must be in the surface map's `items`.
- `backend/app/compositions.py`: `_changes` names hidden/shown; the proposal summary marks hidden items.
- `backend/app/agent/house_file.py` (`placed_items` carries `hidden`), `backend/app/agent/prompts.py` (composition note), `backend/plugins/compose_room/tool.py` and `backend/app/agent/instructions/designer.md`.
- Frontend: `frontend/src/components/inspector/RoomView.tsx`, `frontend/src/lib/api.ts` (`CompositionReport.items`), `frontend/src/routes/Rooms.tsx` (hidden badge).
- Tests: `test_composition_contract.py`, `test_compose_room.py`, `test_house_file.py`, `--blender` `test_composition_blender.py`, and a Vitest test for `RoomView`.
- No migration: compositions are JSON documents and `hidden` is optional.
- Relation to other changes in the 2026-10-18 review batch: the change that removes the turntable viewer link from the Measured Rooms page edits the same studio-ui requirement. Whichever change lands second rebases its delta on the other.
