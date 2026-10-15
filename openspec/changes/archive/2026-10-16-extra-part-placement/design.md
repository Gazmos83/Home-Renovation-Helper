## Context

`ExtraPartIn` (`backend/app/blender/schemas.py:263`) has no position. `_extra_boxes` (`backend/app/blender/generators/build_custom_build.py:532`) stacks every piece flat, 200 mm right of the build. Modules and wall shelves carry a left/front/bottom corner in the build's frame (x right, y back, z up), and `_frame` and `rules.overall` derive the frame from them. Extras sit under `MOD_extras` at the origin, in the `extras` layer. The generator already draws arbitrary convex meshes: `Placement` takes `verts` and `faces` (used by the carcass side folds and the back prism), so turned and cut pieces need no new Blender mechanism. The inspector's explode leaves `MOD_extras` in place (`frontend/src/lib/inspector.ts:39`).

## Goals / Non-Goals

**Goals:**
- An extra part can be drawn assembled, piece by piece, including pieces set at an angle with ends cut to fit, so the model view shows the real design.
- Existing documents draw exactly as before.
- The Designer can place, move, turn, cut or unplace an existing extra part without removing and re-adding it.
- The schema check, the overall size and the drawing agree exactly on where every corner is.

**Non-Goals:**
- Curved parts, notches, half-laps or joinery geometry.
- A change to cut-list sizes, grain, banding, drilling or pricing (end cuts only add a note).
- Frontend changes, or exploding extras with the modules.

## Decisions

**One placement per piece, exactly `qty` entries.** Slats and frame members are usually several pieces at different positions; a partial list would show a half-assembled piece and is rarely meant. A mismatch is refused by name. *Alternative:* a start position plus a step. It is compact for slats but cannot express a frame.

**Base orientation by axes, then at most two named turns.** `length_along` / `width_along` set the square-on pose, matching the spec's wording elsewhere ("along height or depth"). Angles are then added as:
- `roll_deg`: a turn about the piece's length line, positive turning width towards thickness;
- `tilt`: `towards` an axis other than `length_along`, plus `angle_deg`. The length turns towards that axis about the axis perpendicular to both, positive towards the axis's positive direction.

Roll is applied first, then tilt, both about the reference corner. Every pose stays expressible in words ("length along x, tilted 30° towards z"), which a cheap model and the owner can both read. Two turns cover braces, raked legs, angled trim and splayed slats. *Alternative:* free Euler angles `rotation_deg (x, y, z)`. It is fully general, but the order of the angles is easy to get wrong and hard to read back to the owner. A compound case two turns cannot reach would be a later generator-extension request.

**Angles bounded to −89…89 and not 0.** 0 is refused rather than ignored, so the stored document never carries a no-op. ±90 is an axis swap and belongs in `length_along` / `width_along`.

**End cuts on the part, not the placement.** All pieces of a part share one cut-list row, so they share one cut. A positive angle shortens the edge opposite the reference edge by `size × tan(angle)`; a negative one shortens the reference edge. The stated length is therefore always the longest edge, the length the workshop measures, and the cut-list length does not change. With start +a and end −a you get a parallelogram (a brace between parallel rails); with +a and +a you get a trapezoid (a mitred frame member). A cut that leaves an edge of zero length or less is refused.

**One geometry helper in `derive.py`.** `extra_piece_corners(part, placement, thickness)` returns the 8 corners in the build's frame. It builds the local prism (length u, width v, thickness w, with the end cuts applied to the u coordinates of the cut edge), then applies the roll about u, the tilt about u × towards, the axis mapping and the translation to the corner. The schema's envelope check, `rules.overall`, `_frame` and the generator all call it. The generator passes the corners as `Placement(verts=…, faces=…)` with the six quad faces, the way the fold prisms are drawn. Unplaced parts with end cuts use the same helper at the laid-flat position, so they show their cuts too.

**Drawing hierarchy unchanged.** Pieces stay under `MOD_extras` and the `extras` layer. Object names, the layer map, the cut-list module filter and explode keep working. `_override_count` handles an overridden quantity as today: copies are added beside the last piece, and surplus pieces are dropped.

**Revision.** `PackageChanges.extra_parts: dict[Slug, ExtraPartChange]` mirrors `wall_shelves: dict[Slug, WallShelfChange]`. `ExtraPartChange` has `placements` (a list; an empty list unplaces the part) and `end_cuts` (an object, or null to make the ends square), and at least one is required. An unknown id is refused with the known list. The count is checked against the part's current `qty`, and the full validation re-checks it. Equal-value changes are dropped as for other fields.

## Risks / Trade-offs

- [The model writes wrong positions or angles, so pieces float, overlap or point the wrong way] → the Workbench screenshot after every build and the Reviewer catch it. The Designer instructions carry one worked brace example. Placement is drawing only, so a wrong angle never changes the cut list or price.
- [Cut angles that don't match the tilt leave a visible gap or overlap] → this is the honest picture of the stated cuts. For a brace whose width lies in its tilt plane, cuts equal to the tilt give plumb ends (between posts), and cuts of 90° less the tilt give level ends (between rails). The Designer instructions and the import guide state this rule.
- [A placed piece shifts the overall size when there is no envelope] → intended, and the dimension lines follow. Documents with an envelope are unaffected beyond the containment check.
- [Exploded view leaves placed extras in place while modules move apart] → accepted; it is the existing behaviour for `MOD_extras`.

## Migration Plan

None. The fields are optional, and stored versions validate and draw unchanged. Rollback removes the fields; any version that used them would then be refused by name, which is the ladder's normal behaviour.
