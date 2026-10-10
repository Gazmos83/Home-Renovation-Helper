## Context

A module's interior is derived in `custom_build/derive.py` and drawn as axis-aligned cubes in `generators/build_custom_build.py`. Both files already share `interior()` for shelf heights and bays. `_module_boxes` returns `(size, centre)` millimetre boxes; there is no rotation and no n-gon. `overall()` and `_boxes_overlap` use each module's stated `width` × `depth` × `height`. Revisions pass through `revise.py`; `from_mm` must join `OPTIONAL_FIELDS` / list membership in `measurements.py` the same way `divider_positions_mm` did.

See proposal.md for motivation. Specs: furniture-packages (fold contract), design-agents (summary and `from_mm` check), design-import (guide), design-guidelines (span), cut-list-pricing (mitre notes).

## Goals / Non-Goals

**Goals:**
- One fold-profile helper in `derive.py`, used by validation, the cut list, `overall()`, overlap, shelf span and the generator.
- Documents with no `side_folds` keep the same rows, ids and model.
- The model states the owner's millimetre and degree; code does the trigonometry.

**Non-Goals:**
- Doors, dividers or adjustable shelves on a folded module (refused; later changes).
- Perpendicular-to-face board thickness (v1 keeps the side's thickness along X, so the generator can rotate a cube of thickness `t`).
- Kerf-bending a single board, or encoding a net polygon as the cut-list length × width.
- Live Blender, the render guard, or the bpy allow-list.

## Decisions

1. **`side_folds` is a list of objects, not `left_fold` / `right_fold` fields.** One shape covers one or both sides and matches `fronts` / `wall_shelves`. `ModuleChange.side_folds` replaces the whole list; `[]` clears, like `divider_positions_mm`.
   - *Alternative:* `left_fold` and `right_fold` objects. Rejected: two optional nested objects plus two clear sentinels, and `measurements.field_value` still would not see `from_mm` without extra paths.

2. **Shared `fold_profile(module, t, b)` in `derive.py`.** Returns, in the module's own millimetre frame:
   - each side's outer and inner X as a function of Z (height folds) or Y (depth folds), as two vertices per side (kink + far end);
   - `inset_mm` at the far end, already rounded;
   - the axis-aligned bounding box relative to the module origin (negative X or Y when `towards` is `outside`).
   `inset_mm(h, angle_deg) = round_half_away(h * tan(radians(angle_deg)))` with `round_half_away` implemented as `int(math.floor(abs(x) + 0.5))` on the non-negative inset. `schemas.py` calls the same helper so a pinch or a 0 mm inset is refused with the same figure the cut list will use.
   - *Alternative:* compute tan in the generator only. Rejected: the cut list would drift from the model, as the even shelf step did before `interior()`.

3. **Two rectangular side boards, the upper (or rear) one rotated.** The generator keeps `_box` for every rectangular part. For the folded segment it creates the same cube, then sets `rotation_euler` so the board's join edge coincides with the lower (or front) board's join edge, rotation around Y for a height fold and around Z for a depth fold, sign from `side` × `towards`. The back, whose outline is not a rectangle, is the one new primitive: `mesh.from_pydata` in the back plane, still one object named by its cut-list id.
   - *Alternative:* one trapezoidal mesh for the whole side. Rejected: the shop cuts two rectangles and mitres them; the cut list would lie.
   - *Alternative:* live `bpy.ops.mesh.bisect`. Rejected: ladder step 2 is headless from spec, and the allow-list is out of scope.

4. **Cut-list rows stay rectangles.** Non-rectangular leftovers (the back, a top that is a trapezoid in plan on a depth fold) are listed as the grain-aligned bounding rectangle. Notes name the mitre or net shape. Sheet packing and toom classification stay as they are; the existing "notes name mitres" rule marks the row for review.
   - *Alternative:* add polygon parts to the CSV. Rejected: every packer and price path assumes length × width.

5. **Stated size is the unbent box; bounds are computed.** `module.width` at the bottom (or front) does not change when a fold is added, so a revision can add a fold without rewriting width. `overall()`, envelope fit, overlap and `room_fit` call `fold_profile` (or a `module_bounds` wrapper) and use that AABB. `_boxes_overlap` in `schemas.py` switches to those bounds.

6. **Along-slope length of the folded segment** is `round_half_away(run / cos(radians(angle_deg)))`. For the motivating numbers: run 900 mm, 26°, inset 439 mm, upper length 1001 mm, inner depth 388 mm.

7. **Measurement check.** Add `side_folds` to `OPTIONAL_FIELDS` and treat it as a list whose compared values are each fold's `from_mm` (same membership path as `divider_positions_mm`). Degrees are ignored by `lengths()` already (it only matches mm/cm/m).

8. **Designer defaults live in the instructions, not the schema.** The schema requires `along` and `towards`. `designer.md` says: for "a 26 degree bend from 1100 mm" on a named left/right side, write that fold; if the owner did not say height vs depth or inside vs outside, restate `along: height` and `towards: inside` in the change list and wait until the owner says the list is complete. An edge bevel still has no field.

9. **Serializer.** Omit `side_folds` when empty, so stored documents without a fold match today's JSON.

## Risks / Trade-offs

- [The Designer invents `bevel_mm` instead of `side_folds`] → Instructions give one worked example of the owner's sentence; unknown fields still become generator-extension requests.
- [Rotated cubes leave a hairline gap or overlap at the join] → Position from the shared profile's kink vertices; the `--blender` test asserts the join within 0.1 mm and the upper board's angle within 0.1°.
- [Bounding-rectangle backs overstate sheet use] → Notes name the net shape; pricing already marks mitres for review. A net-shape packer is a later change.
- [Horizontal thickness on a rotated board is slightly more than `t`] → Accepted for v1; the cut list still issues an 18 mm board. Perpendicular thickness would need a wedge at the join.
- [`--blender` suite runtime] → One new fixture: the 800 × 2000 × 400 mm cabinet with the 26° left height fold, built with no render.

## Migration Plan

No database or file migration. Existing specs omit `side_folds` and derive as before. Rollback is a revert. A spec stored with `side_folds` would then be refused by name, which is the documented generator-extension behaviour.
