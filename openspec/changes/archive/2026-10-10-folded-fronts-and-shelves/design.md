## Context

`carcass-side-folds` already shares `fold_profile` / `module_bounds` / `min_inner_width` across validation, the cut list and the generator. Overlay fronts today are axis-aligned rectangles from `front_layout` (unbent `width`, 3 mm gap). The back of a folded module is already an n-gon in the back plane (`mesh.from_pydata`). `_check_folds` refuses `fronts`, `dividers` and `adjustable_shelves`.

See proposal.md for motivation. Specs: furniture-packages (fronts and adjustable on a fold), hardware-drilling (split side rows), design-agents (instructions), design-import (guide).

## Goals / Non-Goals

**Goals:**
- One front-outline helper on `fold_profile`, used by validation, the cut list and the generator.
- Rectangular fronts stay rectangles (depth folds; the unfolder-side door of a height fold).
- Documents with no `side_folds` keep the same front rows, hinge lines and pin entries.

**Non-Goals:**
- Dividers on a folded module (still refused).
- Non-rectangular drawer *boxes* (the box stays a rectangle at min inner width).
- Drawing hinge cups, plates or pin holes in the model.
- Live Blender, the render guard, or the bpy allow-list.

## Decisions

1. **Front outline is the outer carcass silhouette in the front plane, inset by 1.5 mm.** Same overlay contract as today. Vertices come from the side profile at the front (`y = 0`): left outer X at each height (0, each height-fold `from_mm`, height), then right, then close. Several doors of one entry clip that polygon to vertical strips at `k * unbent_width / count`. A strip that is still a rectangle (four axis-aligned corners) uses `_box`; otherwise `_prism` like the back.
   - *Alternative:* inscribed rectangles at min width. Rejected: the owner's 6.2 cabinet would lose the upper left corner of the door.
   - *Alternative:* split the front entry at `from_mm`. Rejected: the Designer would have to restate two fronts for one door the owner already has.

2. **Bounding rectangle on the cut list.** `l` and `w` are the axis-aligned bounds of the net, grain vertical for doors. Notes name the net. Equal doors that share a rectangle keep quantity as today; a left n-gon and a right rectangle become two rows (`{id}-door-1` stays one id with qty 2 only when both nets match — they will not, so qty 1 each, or keep one id with qty 2 and the larger bound). **Use two rows when the nets differ:** `{module}-door-{entry}-1` and `-2` counted left to right, so the shop gets the true bound of each leaf. When they match, keep `{module}-door-{entry}` quantity `count`.
   - *Alternative:* one row with the max bound and qty 2. Rejected: the left leaf is smaller; the cut list would overstate that board.

3. **Drawer boxes use `min_inner_width` over the drawer's z-range**, then runner clearance. The drawer *front* still follows the outer outline (may be an n-gon if it spans the kink).

4. **Adjustable shelves reuse `_folded_shelf_widths`.** Clearance is subtracted after the min inner width, floored. Pin drilling maps each hole height onto the side piece that contains it. Heights on the upper board are `hole_z - from_mm` measured along the slope: `slope_mm(hole_z - from_mm, angle)` from that board's lower end. The drilling part id is the cut-list side-board id.
   - *Alternative:* keep listing `{id}-side` even when that row is gone. Rejected: the shop would not know which board to drill.

5. **Minimum front size** is judged on the remaining width of each leaf at every sample height (bottom, top, each kink). Below `MIN_FRONT_MM`, refuse `modules[n].fronts`.

6. **Archive `carcass-side-folds` first.** This change MODIFIES that change's fold requirement. Apply this change on the tree that already has the fold field.

## Risks / Trade-offs

- [Hinges on a sloped side] → Cups stay on the door (front plane); plates on the sloped board are listed with a note and marked for review by existing machining-note rules if the notes name the slope. The model does not draw them.
- [Two door rows instead of qty 2] → Tests that assume `{id}-door-1` qty 2 on the starter will need a folded-starter fixture; unfolder documents stay qty 2.
- [`--blender` suite runtime] → One new fixture: the 26° cabinet with two doors and four shelves, built with no render.

## Migration Plan

No database or file migration. Existing specs without folds are unchanged. Rollback is a revert. A folded spec with doors that was refused before this change becomes valid.
