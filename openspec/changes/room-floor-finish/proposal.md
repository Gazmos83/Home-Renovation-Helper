## Why

In the end-to-end review of 2026-10-15 the owner asked to tile the whole floor of `Wohnen` in its turntable. Today the floor material is hard-coded: `_build_materials` in `build_room_scene.py:124` sets one brown, and the apartment shell sets another (`build_shell._COLOURS`). Only a restyle variant changes it, and then only to one plain colour. A floor-layer item can stand in for a rug, but it is a single plain rectangle. It cannot follow an L-shaped outline and has no tile pattern. On 2026-10-18 the owner chose a room floor finish: one field covering the whole outline, with tile size, tile colour, grout colour and grout width. The schema cannot express this, so this is a generator-extension request (ladder step 2).

## What Changes

- **A `floor` finish on the composition document.** It is optional and top-level, beside `scope` and `items`. It holds:
  - `tile_width_mm`, `tile_length_mm` (20 to 2500);
  - `tile_colour`, `grout_colour` (`#rrggbb`);
  - `grout_width_mm` (0 to 20; 0 is butted planks);
  - optionally `pattern`, `"grid"` (default) or `"staggered"`. Staggered shifts each row by half a tile, which gives a plank or running-bond floor.

  Unknown fields and values out of range are refused by name. An apartment composition's finish covers every floor of the apartment.
- **It lives in the composition version**, so it is versioned, shown in the confirmation, compared against the previous version ("floor: 600 × 600 mm tiles" / "floor finish removed") and approved with the room. It is not stored in the room's house-file record.
- **The generator draws the tiles procedurally.** The headless composition build gives every floor of the scope a tile material made from Blender's own brick texture node: tile size, joint width, joint colour and row offset. There are no texture files, and the floor geometry is unchanged, so an L-shaped or U-shaped floor is covered exactly as far as its outline reaches. Stills and turntables, draft and final, show the joints. `model.glb` (the 3D view) and the Workbench screenshot show the floor in the flat tile colour.
- **A restyle keeps the finish.** A room style changes walls, ceiling, light and stand-ins as before, but leaves a finished floor as it is. TODO(user): confirm. The alternative is that the style's floor colour replaces the tile colour while the joints stay.
- The `compose_room` tool description, the Designer instructions and the composition note describe the finish. The proposal summary shows it.

No breaking change: documents without `floor` build exactly as before.

Depends on `composition-ceiling-layer` (in progress in the working tree) and `hidden-room-items` (proposed in the same 2026-10-18 batch, priority 8). The `room-composition` delta here is written on top of both. If `hidden-room-items` is dropped or lands later, rebase this delta before archiving.

Ladder step 2 (generator extension: schema, checks and composition generator). Agents touched: the **Designer** (`compose_room`); the Builder renders a composition unchanged. The **render guard** is **not affected**: renders still go through it with the same tiers. The **bpy allow-list** is **not affected**: the material is made in a checked-in headless generator, not a live script.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `room-composition`: the document gains an optional `floor` finish. The headless build gives every floor in the scope the tile material, and the GLB and screenshot show the tile colour.
- `restyle-variants`: a room style leaves a finished floor unchanged.

## Impact

- `backend/app/blender/composition_contract.py`: `floor` in the top-level optional keys, parsed into a normalised finish (`_parse_floor`), and carried into the stored document.
- `backend/app/blender/generators/_composition.py`: after `_build_shells`, give the `Floor` / `Floor_<room>` meshes a tile material when the document has a finish. For export, swap in a flat material of the tile colour and swap back afterwards (`build_composition.py`). The report states the finish.
- `backend/app/blender/generators/render_restyle.py`: `apply_room` skips floor surfaces when the document has a finish.
- `backend/app/compositions.py`: `_changes` and the proposal summary. `backend/app/agent/house_file.py` and `prompts.py`: the composition listing and note carry the finish. `backend/plugins/compose_room/tool.py` gains an optional `floor` argument and passes it to `compositions.propose`. `backend/app/agent/instructions/designer.md` describes it.
- Frontend: none required. The Rooms page item list is unchanged, and the 3D view shows the GLB's floor colour.
- Tests: `test_composition_contract.py`, `test_compose_room.py`, `test_house_file.py`, the restyle tests, and `--blender` `test_composition_blender.py`.
- No migration: documents are JSON and `floor` is optional.
