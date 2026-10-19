Before starting: `composition-ceiling-layer` is committed and archived. `hidden-room-items` is applied first (this delta builds on its text). This change is about 90 minutes of work. pytest is not run per task (decided 2026-10-18). Tests are written with the code and run in the batch check (4.1).

## 1. Contract and service

- [x] 1.1 In `backend/app/blender/composition_contract.py`, accept an optional top-level `floor`. Add `_parse_floor`, which handles:
  - the fields, ranges, colours and `pattern` with `grid` as the default;
  - refusing an unknown field by name.

  Write tests in `backend/tests/test_composition_contract.py` for "Tiled floor accepted", "Plank floor accepted", "Unknown floor field", "Tile too small" and "Unknown pattern". Verify with `uv run ruff check .`.
- [x] 1.2 Add an optional `floor` argument to `ComposeRoomArgs` and pass it through `compositions.propose` into the document. In `backend/app/compositions.py`:
  - add the finish to the proposal summary;
  - make `_changes` emit "floor: …" when the finish is added or changed, and "floor finish removed" when it is dropped.

  Carry the finish in `house_file.compositions` and show it in `prompts.composition_note`. Describe it in `backend/app/agent/instructions/designer.md`. Write tests in `test_compose_room.py` (preview with a finish, change lines, tool schema) and `test_house_file.py` (note line). Verify with `uv run ruff check .`.

## 2. Generator

- [x] 2.1 In `backend/app/blender/generators/_composition.py`, add `_apply_floor_finish`. It gives every floor surface a Brick Texture tile material: nodes by type, object coordinates, grid or staggered. Call it from `build_scene` and add `floor` to the report. Write `--blender` tests in `test_composition_blender.py`:
  - "Tiles across an L-shaped floor": every floor polygon uses the tile material, and the brick node holds the stated width, row height and mortar size in metres;
  - "No finish, default floor".

  Verify with `uv run ruff check .`.
- [x] 2.2 In `backend/app/blender/generators/build_composition.py`, put a flat tile-colour material on the floors (with `diffuse_color`) for the screenshot and `export_glb`. Restore the tile material in a `finally` block before saving `model.blend`. Write a `--blender` test for "Finish in the 3D view": the GLB's floor material base colour equals the tile colour, and the saved `model.blend` floor uses the tile material. Verify with `uv run ruff check .`.

## 3. Restyle

- [x] 3.1 In `backend/app/blender/generators/render_restyle.py`, make `apply_room` skip floor surfaces when the document has a finish. Write a test for "Tiled floor kept" beside the existing room-restyle tests (`--blender` where the existing ones are). Verify with `uv run ruff check .`.

## 4. Checks

- [ ] 4.1 Batch check: pytest and the `--blender` suite are deferred to the batch check after the last change of the 2026-10-18 review batch. Run them there, skipping the RunPod and offload tests and using a throwaway `TEST_DATABASE_URL`:
  - `uv run pytest -m "not slow"`;
  - `uv run pytest --blender tests/test_composition_blender.py` and the restyle Blender tests;
  - `uv run ruff check .`.

  All must pass.
- [ ] 4.2 Browser pass (render tier **draft**):
  - in a conversation for `Wohnen`, ask the Designer for 600 × 600 mm light grey tiles with 3 mm grout across the whole floor, and confirm. The confirmation shows "floor: …";
  - the Measured Rooms 3D view shows the floor in the tile colour;
  - render a `draft` turntable behind the guard. The joints cover the whole floor, inner corner included;
  - a `draft` restyle variant of that version keeps the tiles.
