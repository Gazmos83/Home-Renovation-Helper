## Why

The owner asked to make one carcass shelf deeper than the others ("second shelf from the bottom 500 mm deep, rest 400 mm") and the Designer correctly refused: in a module, every shelf is cut at the module's back-reduced depth. There is no per-shelf depth field, so the request cannot be expressed yet and was recorded as a generator-extension request. Deeper or shallower individual shelves are ordinary cabinetry (a display shelf that sticks out, a recessed shelf for cables or a shallower upper board).

## What Changes

1. **Per-shelf depth on a module.** A module accepts an optional `shelf_depths_mm` list: one entry per shelf, lowest first, counting fixed and adjustable shelves together (same indexing as `shelf_positions_mm` and `shelf_kinds`). Each entry is either a whole-millimetre cut depth or `null` (use the module's back-reduced depth). Without the field, every shelf stays at the back-reduced depth as today.
2. **Flush face.** A module accepts an optional `shelf_depth_align` of `"back"` or `"front"` (default `"back"` when depths are set). `"back"` keeps each custom shelf's rear on the carcass inner rear (deeper boards stick out the front; shallower boards recess from the front). `"front"` keeps each custom shelf's front on the side fronts (deeper boards stick out the back; shallower boards leave a gap at the back). One align applies to every custom depth on that module.
3. **Validation.** A list of the wrong length, a depth below a small minimum, a depth that cannot fit a folded module's inner depth at that shelf's height, or (when an envelope is set) a board that leaves the envelope is refused, naming the field. An adjustable shelf whose stated depth does not cover both shelf-pin columns (exact front and rear setbacks from the data sheet) is refused, naming `shelf_depths_mm`.
4. **Cut list and model.** Each shelf board is cut and drawn at its own depth and y-placement from the align rule. Rows of one kind group by cut width and depth (several depths become `{id}-shelf-<n>` / `{id}-adjustable-shelf-<n}` as for mixed widths today). Dividers, sides, top and bottom stay at the back-reduced carcass depth.
5. **Bounds.** Without an envelope, `overall` depth grows to include a shelf that sticks out past the carcass. Overlap checks use the same expanded shelf boxes.
6. **Revisions.** `revise_package` sets and clears `shelf_depths_mm` (`[]` clears) and `shelf_depth_align`. Clearing depths clears the align. The requested-measurement check accepts an absolute depth for a list entry the way it does for `shelf_positions_mm`.
7. **Designer.** The piece summary shows each module's per-shelf depths and align when set. The Designer instructions describe the fields with the motivating example, and never tell the owner there is no field for a deeper or shallower shelf.
8. **Import guide.** The design-import guide names both fields.

A document that omits both fields derives and draws exactly as before.

**Ladder step:** 2 (generator extension). **Agents:** Designer (schema, instructions, piece summary, `revise_package`, import guide) and Builder (headless generator draws per-shelf depths). Intake, Reviewer, Researcher, Lighting & materials and Foreman are untouched. **Render guard:** not affected. **bpy allow-list:** not affected; no live script is added.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `furniture-packages`: a module may state per-shelf depths and a flush align; shelves are cut and drawn at those depths; overall/overlap account for protruding shelves.
- `hardware-drilling`: an adjustable shelf with a custom depth must still cover both pin columns when setbacks are exact; pin columns stay on the sides at the carcass setbacks.
- `design-agents`: piece summary, requested-measurement check, and Designer instructions cover `shelf_depths_mm` and `shelf_depth_align`.
- `design-import`: the import guide describes both fields.

## Impact

- `backend/app/blender/schemas.py`: `shelf_depths_mm` and `shelf_depth_align` on `ModuleIn` / `ModuleChange`, length and fit checks.
- `backend/app/blender/custom_build/derive.py`: per-shelf depth and y-placement, cut-list row grouping by depth, `module_bounds` / overlap boxes for protruding shelves, docstring rule table; optional pin-coverage check fed by hardware inputs.
- `backend/app/blender/generators/build_custom_build.py`: shelf boxes use each board's depth and y centre; `--blender` suite must run.
- `backend/app/agent/revise.py`, `measurements.py`, `prompts.py`, `instructions/designer.md`, import template / guide.
- Tests in `backend/tests/` (schema, derive, revise, piece note, instructions, drilling, `--blender`).
- No migration (fields live in stored spec JSON). No frontend change. No new dependency.
