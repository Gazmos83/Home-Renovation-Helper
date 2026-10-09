## Why

The owner's second app check of 2026-10-09 (`docs/App Check_2 09-10-2026.md`) found two requests the Designer could not carry out: "4 shelves 355 mm apart" and vertical dividers. Both were refused with "no field". The Designer understood the request, but the spec has no way to state it:
- a module holds shelves only as counts, and the generator always spaces them evenly;
- nothing in the schema, the generator or the cut-list rules knows a divider.

The predecessor app had the same limit. Its exact positions came from free-form bpy in the owner's Claude Code workshop (`blender-design-package` skill with the Blender MCP), not from the app.

The owner chose to grow the spec first (ladder step 2) and to test the result before anything else from that app check. If revisions are still not good enough after this test, the owner will consider revising the spec-only hard rule (CLAUDE.md §1) in a separate change.

## What Changes

1. **Shelf spacing and positions on a module.** Two optional module fields; a module may state one or the other, never both:
   - `shelf_spacing_mm` is the clear gap between boards. The first shelf sits one gap above the top face of the bottom panel, and each next one sits one gap plus one board thickness higher. For "4 shelves 355 mm apart" with 18 mm boards, the undersides are at 355, 728, 1101 and 1474 mm. The app does this arithmetic, never the model.
   - `shelf_positions_mm` lists the height of each shelf's underside above the top face of the bottom panel, for uneven positions. It has one entry per shelf, counting fixed and adjustable shelves together.
   - A shelf that does not fit under the top panel, positions that overlap, or a list of the wrong length is refused, naming the field.
   - Without either field, shelves are spaced evenly as today.
2. **Full-height vertical dividers.**
   - A module accepts `dividers` (a count, spaced evenly) and optionally `divider_positions_mm`: the distance from the inner face of the left side to each divider's left face.
   - A divider runs between the bottom and top panels, in the carcass material, at the back-reduced depth.
   - Shelves are then cut per bay, at the same heights in every bay. The cut list, the confirmat count, the shelf-pin count and the shelf-pin drilling (on both faces of each divider) follow.
   - The shelf-span design rule is judged per bay.
3. **Revisions.**
   - `revise_package` can set and clear the new fields. Setting a spacing clears stored positions, and setting positions clears a stored spacing; the change lines say so.
   - The requested-measurement check accepts an absolute length for a field the module has not set yet, and for a positions list it checks that the value is in the revised list.
4. **Designer.**
   - The piece summary shows each module's spacing or positions and its dividers.
   - The Designer instructions describe the new fields, with one example each.
5. **Owner test gate.** The change ends with a test by the owner in the chat: shelves 355 mm apart, then dividers, as headless builds with blockout screenshots and an optional `draft` turntable. The other app-check items (the "Inspect version N" button and per-module sizes in the exploded view) wait for this test.

A document that uses none of the new fields derives the same cut list, hardware, drilling and model as before.

**Ladder step:** 2 (generator extension). **Agents:** Designer (prompt, piece summary, `revise_package`) and Builder (the generator draws the new parts). Reviewer, Intake and Foreman are untouched. **Render guard:** not affected; builds stay headless and renders keep their tiers. **bpy allow-list:** not affected; no live script is added.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `furniture-packages`: modules accept shelf spacing or positions and vertical dividers. Shelves are drawn and cut per bay at the stated heights, and the even-spacing rule applies only when no spacing or positions are stated.
- `hardware-drilling`: shelf-pin holes are listed on both faces of each divider as well as on the sides, and counted per bay.
- `design-guidelines`: the shelf span is measured per bay when a module has dividers.
- `design-agents`: the Designer's piece summary shows spacing, positions and dividers. The requested-measurement check covers fields not yet set and position lists.

## Impact

- `backend/app/blender/schemas.py`: `ModuleIn` and `ModuleChange` fields, plus the relationship checks.
- `backend/app/blender/custom_build/derive.py`: shelf heights and bay widths, divider and per-bay shelf rows, confirmat and pin counts, pin drilling on dividers, docstring rule table.
- `backend/app/blender/generators/build_custom_build.py`: draws dividers and shelves per bay at the calculated heights. The `--blender` suite must run.
- `backend/app/agent/revise.py`, `backend/app/agent/measurements.py`, `backend/app/agent/prompts.py` (piece summary), `backend/app/agent/instructions/designer.md`.
- `backend/app/guidelines/checks.py` (shelf span per bay) and `backend/app/guidelines/hardware_inputs.py` if pin inputs depend on dividers.
- No migration: the fields live in the stored spec JSON. No frontend change: dividers appear in the inspector's existing `carcass` layer.
