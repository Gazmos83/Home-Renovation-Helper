## Context

See proposal.md (Why). The current state the approach builds on (with `composition-ceiling-layer` applied):

- `composition_contract._parse_item` builds each item from a fixed key set per type through `_require_keys`. `layer` is the only optional key and is allowed on `stand-in` and `model` only, so an unknown `hidden` is refused today. `compose_room` then records it as a generator-extension request.
- `place_items` checks each item in order: ceiling height, wall end, outline (`_footprint_inside`), openings (`_blocked_opening`, skipped for the floor layer), and overlap against every earlier item (`footprints`). Only standing items (`layer is None`) become rule subjects. Each resolved item carries id, room, size, centre, rotation and, for a ceiling item, `base_mm`.
- `_composition.build_scene` places every resolved item and appends one report entry per item: `id`, `type`, `stated_mm`, `final_mm`, `lowest_mm` and, for a model, `scale`. It collects all item meshes in `scene.item_meshes`, and `surface_map` puts them all under the single `items` surface. Mesh names in the GLB are Blender object names, so they are unique: a stand-in is `STAND_<id>`, while imported pieces and models keep their imported names under an `ITEM_<id>` empty.
- `verify_composition` requires every GLB mesh to be in exactly one surface.
- `RoomView.tsx` builds the canvas layer map straight from `report.surfaces` and offers one switch per surface. `PieceModel` hides a mesh when `layerOf` (the first layer listing it) is switched off.
- `render_composition.py` and `render_restyle.py` both rebuild the scene through `build_scene`.
- `compositions._changes` lists added, removed, moved and changed ids. `house_file.placed_items` copies `room`, `placement` and `layer`. `composition_note` marks the layer.

## Goals / Non-Goals

**Goals:**
- Hide one item in the 3D view at once, with nothing saved.
- Save "keep it in the layout, leave it out of the picture" in a room version, so that a draft or final render can be made without that item.

**Non-Goals:**
- Saving viewer switch states per version or per owner.
- Hiding parts of a piece (single cut-list parts). The piece inspector already has layer switches.
- Showing hidden items as ghosts or outlines in the 3D view. A hidden item is not built, so there is nothing to show.
- A button on the Rooms page to toggle the saved flag. It is set through the Designer's `compose_room`, like every other composition change. TODO(user): a direct "Hide in renders" action could follow later if typing it proves slow.

## Decisions

1. **`hidden` is a common optional key for all three types.** `_parse_item` adds `hidden` to the optional set for every type, next to `layer` for stand-ins and models. It must be a boolean. Only `true` is kept, so the normalised form of `hidden: false` matches a document without it, and `_changes` reports no change. Rejected alternative: a separate `hidden_items` list on the document, which would duplicate ids and drift from the item list.

2. **Shape checks stay, interaction checks go.** A hidden item keeps the ceiling-height, wall-existence, wall-end and outline checks, and a hidden piece still goes through `_piece_size`'s approval check. These keep the stored layout valid when it is shown again. It is not passed to `_blocked_opening`, it is not added to `footprints` (so later items are not compared with it), it is not compared with earlier items, and it is not added to the rule subjects. Showing it again is a new `compose_room` call, so every check runs again then. Rejected alternative: keeping the overlap check, which would block moving other furniture into the spot of an item the owner has set aside. The owner can confirm or reverse this decision (TODO(user) in the proposal) without changing the schema.

3. **The resolved item carries `hidden: true`.** It is added beside `base_mm`, so the generator reads one block, as the ceiling-layer design chose.

4. **The generator skips, the report still lists.** `build_scene` appends `{"id", "type", "hidden": true}` for a hidden item and places nothing. `composition_unbuilt_pieces` in `runner.py` skips hidden pieces, so a hidden piece whose build was later deleted cannot fail the room build. Renders, restyles and the detail pass get no special handling, because they all go through `build_scene` or the saved `model.blend`.

5. **Per-item meshes in the report, surface map unchanged.** Each built item's report entry gains `name` (the stand-in or model name, or `"<package_id> v<version>"` for a piece) and `meshes` (the GLB node names of its meshes, taken from the objects that `_place_*` returns). The surface map keeps one `items` surface, so `verify_composition` and every older consumer stay valid. `verify_composition` gains one check: every listed item mesh is under `items`, and no mesh is listed for two items. Rejected alternative: one surface per item in the surface map. That would rename surfaces older reports already have, and restyle's `_surface_kind` would have to learn new labels.

6. **RoomView builds item layers on the client.** When every built report item has `meshes`, `RoomView` drops the `items` surface from its switch list. It adds one layer per item, keyed `item:<id>` and labelled with `name`, to the canvas layer map in front of the surfaces, so `layerOf` finds the item first. It also offers an "All items" button that works like "All walls". The switch state lives in the component's `useState`, so it resets when the view remounts or the version changes. With older reports, nothing changes.

7. **Designer surface.** One sentence in the `ComposeRoomArgs.items` description and in `designer.md`: "`hidden: true` keeps an item in the layout but leaves it out of the build and every render; to show it again, compose without the flag". `composition_note` appends "(hidden)". The proposal summary appends ", hidden" to the item's line. `_changes` emits `hidden: <id>` / `shown: <id>` when the only difference is the flag, before the general `changed:` line.

## Risks / Trade-offs

- [The owner forgets an item is hidden and wonders where the sofa went in a final render] → The confirmation summary, the Rooms page list and the composition note all say "hidden". The Designer reads the note.
- [A hidden item placed where another item now stands cannot be shown again without moving one of them] → `compose_room` refuses naming both ids, so the Designer can move one. This is the price of decision 2.
- [GLB node names are sanitised by the three.js loader] → `layerOf` already compares through `PropertyBinding.sanitizeNodeName`, and the item mesh names come from the same Blender objects as the surface map.
- [A large composition gets many item switches] → `composition_max_items` already caps the item count. The switches wrap like the wall switches do.

## Migration Plan

None. Stored versions have no `hidden`, and old reports have no per-item `meshes`, so they keep the single items switch. Rollback: revert the change. Documents carrying `hidden` are then refused by name, and new reports' extra keys are ignored.
