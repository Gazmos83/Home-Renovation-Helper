## Why

A slatted door (Lamellen, a 3D look) can only be copied today as a list of placed extra parts. Each slat is one placement with hand-worked coordinates, so adding or removing a slat means rewriting every position. Resizing the door leaves the slats where they were. The owner wants to try the number of slats as a style choice with one value. The Höffner "Kommode Harmony" (article 13207807, right door with "Akzentstarke Lamellen 3D-Optik") prompted this: the import found nothing in the spec that could hold the slats.

## What Changes

- A door entry MAY carry `slats`:
  - `count`: slats per door leaf, 1–40.
  - `width`: each slat's face width in mm.
  - `material`: a material slot. The slot's thickness is how far the slats stand proud of the door.
  - `orientation`: optional, `vertical` (default) or `horizontal`.
  - `margin_mm`: optional, default 0. The distance from every edge of the leaf to the slats.
  - `leaves`: optional. The leaves of the entry, counted from 1 on the left, that carry slats; the default is every leaf.
- Slats follow their door. Vertical slats run the door's height less the two margins and are spaced evenly across its width; horizontal slats run its width and are spaced over its height. The outer slats lie on the margins. Changing the door's size, `count`, `width` or `orientation` re-spaces them with no other edit.
- Refused by name before Blender runs:
  - a gap between slats under 3 mm;
  - a margin that leaves no room for the slats;
  - a `leaves` number outside the entry's count, or a repeated one;
  - a material slot that does not exist;
  - slats on a module with `side_folds` (not supported yet).

  `slats` on a drawer or flap is refused as an unknown field.
- Slats are cut parts. Each slatted door row gains one cut-list row, `<door row id>-slat`, with quantity count × slatted leaves, cut from its slot's material, and priced like any part. The build draws one object per slat in the `fronts` layer, parented to the module. It shows in `model.glb`, the inspector, the screenshots and every render, and appears in the exploded view.
- A door may carry both slats and a handle, in either orientation. On a slatted leaf the handle is drawn on the slats, standing proud of their face. Its screws then pass through a slat, and its posts may land on a slat or in a gap. Every such leaf carries a **slat-handle warning**:
  - in the cut list, at the end of the slat row's note, so `cutlist.csv` and the inspector's table show it;
  - in the conversation, written by the application: in the confirmation of a create, revise or import that would carry it, and in the Designer's summary of the active build.
- Slats change neither `overall` nor the envelope check, which already ignore fronts and handles. They add no hardware line and no drilling.
- The generator's colour table gains `anthracite` / `anthrazit`, so an anthracite slot shows dark rather than the default beige-grey.
- `revise_package` changes slats through the module's `fronts`, as it changes handles. Change lines and the Designer's context word them, for example "8 slats 30 mm on door 2". The Designer's instructions and the import template's guide describe `slats`.

Ladder step 2 (generator extension): the schema, the derive rules and the headless generator `build_custom_build.py` grow. It touches the **Designer** (revise_package change lines, context summary, instructions) and the **Builder** (headless build). The **render guard** and the **bpy allow-list** are **not affected**: there is no new render path and no live script, and tiers are unchanged. Slat meshes are boxes made by the checked-in generator, like the door panels.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `furniture-packages`: new requirements that a door can carry vertical or horizontal slats, with their cut-list row and drawn objects, and that a handle on slats is drawn on them and warned about in the cut list and the creation confirmation.
- `design-agents`: change lines, the revision confirmation and the Designer's context name a door's slats and the slat-handle warning when set.
- `design-import`: the import template's guide describes `slats`; the import previews show the slat-handle warning.

## Impact

- `backend/app/blender/schemas.py`: a `SlatsIn` model; an optional `slats` on `DoorIn`; refusals for leaves, gaps and margins, an undefined slot, and folded modules.
- `backend/app/blender/custom_build/derive.py`: a `slat_layout(module, materials, t, b)` shared by validation, derive and the generator; one cut-list row per slatted door row.
- `backend/app/blender/generators/build_custom_build.py`:
  - slat boxes in `_add_front_boxes`, under the slat row id, in the `fronts` layer;
  - a handle's front plane moved out by the slat thickness on a slatted leaf;
  - `anthracite` in `_COLOURS`.
- `backend/app/agent/revise.py` (`describe_front`, the confirmation), `backend/app/agent/prompts.py` (the summary's warning line), `backend/app/agent/instructions/designer.md`, `backend/fixtures/packages/templates/import-template.json`.
- `backend/plugins/create_piece/tool.py` and `backend/plugins/design_import/tool.py`: the previews add the slat-handle warnings beside the design-rule warnings.
- Tests: schema, derive, revise, prompts, instructions and the import template; `--blender` build tests.
- Frontend: no code change. Slats are cut-list pieces in the existing `fronts` layer, so the inspector, the layer switches and the cut-list tables show them as they are. A browser pass confirms this.
- Unchanged:
  - pricing code (the new row is priced by its slot like any part);
  - restyle looks (these apply per slot, so a separate slat slot can take its own look);
  - drilling;
  - room compositions (these import `model.glb`).
