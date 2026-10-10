## Why

The owner-test for `carcass-side-folds` asked to put a 26° left bend on a real carcass. That carcass already has doors (the starter has two hinged doors and four fixed shelves). The v1 fold contract refuses fronts, dividers and adjustable shelves on a folded module, so the revision never built. Fixed shelves already derive on a fold; doors and adjustable shelves must too, or a non-rectangular carcass cannot be a cabinet.

## What Changes

1. **Fronts on a folded module.** Overlay doors, flaps and drawer fronts follow the folded carcass outline in the front plane, with the same 3 mm gap. Several doors still split on verticals at equal shares of the unbent width. Each front whose outline is not a rectangle is one n-gon; its cut-list row is the grain-aligned bounding rectangle, with notes that name the net shape. A front whose remaining width at any height is below the minimum front size is refused naming that front.
2. **Drawer boxes stay rectangles**, cut to the smallest inner width along that drawer's height, less runner clearance.
3. **Adjustable shelves on a folded module.** Each board is a rectangle cut to the smallest inner width along its thickness, less the adjustable-shelf clearance, same rule as fixed shelves on a fold. Pin holes are listed on each side board: the unfolder side as today; on a folded side, holes below the kink on the lower or front piece, holes past the kink on the upper or back piece, measured from that piece's own bottom (or front) end.
4. **Hinge plates** on a folded hinge edge sit on the side piece that holds that height (lower or upper), with a note that plates above the kink sit on the sloped board.
5. **Dividers stay refused** on a folded module (bays that change along the fold). A later change can lift that.
6. **Designer and import guide.** Instructions and the import template describe fronts and adjustable shelves on a fold, and drop the v1 "cannot carry fronts or adjustable shelves" line. Bevels stay unexpressible.

Depends on `carcass-side-folds` (the fold field, profile and split side rows). Not **BREAKING** for documents without folds.

**Ladder step:** 2 (generator extension). **Agents:** Designer (schema, instructions, import guide) and Builder (headless generator draws n-gon fronts). Reviewer, Intake, Foreman, Researcher, Lighting & materials are untouched. **Render guard:** not affected. **bpy allow-list:** not affected; no live script is added.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `furniture-packages`: a folded module may carry fronts and adjustable shelves; overlay fronts follow the folded outline; adjustable shelves use the folded inner width.
- `hardware-drilling`: shelf-pin and hinge-plate positions name the split side-board rows on a folded module.
- `design-agents`: the Designer may put fronts and adjustable shelves on a folded module; instructions give the n-gon overlay rule.
- `design-import`: the import template's guide no longer forbids fronts or adjustable shelves on a fold.

## Impact

- `backend/app/blender/schemas.py`: drop the fronts and adjustable-shelves refusals in `_check_folds`; keep the dividers refusal; refuse a front that pinches below the minimum size.
- `backend/app/blender/custom_build/derive.py`: folded front outlines, bounding-rectangle cut-list rows, drawer boxes at min inner width, adjustable-shelf widths, pin and hinge drilling on split side rows, docstring rule table.
- `backend/app/blender/generators/build_custom_build.py`: n-gon overlay fronts in the front plane; rectangular fronts when the outline is still a rectangle. `--blender` suite plus the 26° cabinet with the starter's two doors and four shelves.
- `backend/app/agent/instructions/designer.md`, `backend/fixtures/packages/templates/import-template.json`.
- No migration, no frontend change, no render-guard or allow-list change.
