## Why

Extra parts (frames, slats, braces, trim and anything else the module rules cannot express) have no position in the spec, so every build lays them flat beside the model. The model, inspector, screenshots and turntables therefore show loose boards instead of the assembled piece. The owner needs the model view to give a clear image of what the actual design will look like, including pieces set at an angle such as diagonal braces and angled trim, with ends cut to fit.

## What Changes

- An extra part MAY carry `placements`: one entry per piece (exactly `qty` entries), each giving:
  - the piece's reference corner (`x`, `y`, `z`, in mm in the build's frame, as for modules and wall shelves);
  - its orientation (`length_along`, `width_along`, each one of `x`, `y`, `z`; the thickness takes the remaining axis);
  - optionally `roll_deg`, a turn about the piece's own length line;
  - optionally `tilt` (`towards` an axis, `angle_deg`), which turns the length towards that axis. Both turns pivot at the reference corner.
- An extra part MAY carry `end_cuts` (`across` width or thickness, `start_deg`, `end_deg`). Each end is drawn cut at that angle, so a brace sits flush against the rails it meets. The stated length stays the longest edge, and the cut-list row notes the cuts.
- A placed extra part is drawn at its stated positions, orientation and turns, as exact geometry, in `model.blend`, `model.glb`, the screenshots, the inspector and every turntable. An extra part without `placements` is still laid flat beside the build, so every existing document draws exactly as before.
- When the document has an envelope, every corner of a placed piece, after its turns, must lie inside it; otherwise the document is refused, naming the part. When it has none, those corners count toward the overall size. Unplaced pieces never count.
- `revise_package` gains `extra_parts: {id: {placements, end_cuts}}` to place, move, turn, cut or unplace an existing extra part. `add_extra_parts` accepts the new fields. Change lines describe them before and after.
- The Designer's context and the import template's guide describe the new fields. The guide stops saying that only modules are drawn assembled.
- The cut list keeps every row's quantity and size. End cuts add a note, and hardware, drilling and pricing are unchanged.

Ladder step 2 (generator extension): the schema and the headless generator `build_custom_build.py` grow. It touches the **Designer** (revise_package, context summary) and the **Builder** (headless build). The render guard and the bpy allow-list are **not affected**: no new render path, no live script, and tiers are unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `furniture-packages`: new requirements that an extra part can state where each of its pieces sits, including its angle, and that it can state angled end cuts; unplaced extras keep being laid beside the build.
- `design-agents`: `revise_package` can place, move, turn, cut or unplace an existing extra part; the Designer's context gives each extra part's placement and end cuts when set.
- `design-import`: the import template's guide describes `placements`, `roll_deg`, `tilt` and `end_cuts`, and says that modules, wall shelves and placed extra parts are drawn assembled.

## Impact

- `backend/app/blender/schemas.py`: `ExtraPartIn.placements` and `end_cuts`, the count, axis, end-cut and envelope checks, `ExtraPartChange` and `PackageChanges.extra_parts`.
- `backend/app/blender/custom_build/derive.py`: one shared helper for the corners of a piece after its cuts and turns; `overall()` includes placed pieces; end cuts are noted on the cut-list row.
- `backend/app/blender/generators/build_custom_build.py`: `_extra_boxes` draws placed and cut pieces as vertex meshes, and `_frame` includes them.
- `backend/app/agent/revise.py`, `backend/app/agent/prompts.py`, `backend/app/agent/instructions/designer.md`, and `backend/fixtures/packages/templates/import-template.json`.
- Tests: schema, derive, revise, prompts and import template; `--blender` build tests.
- Frontend: no change. Placed pieces stay under `MOD_extras` and the `extras` layer, so the layer switch and the cut-list "Extra parts" filter keep working.
