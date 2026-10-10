## 1. Schema

- [x] 1.1 Drop the fronts and adjustable-shelves refusals in `_check_folds`; keep the dividers refusal. Refuse a front whose remaining width at any sample height is below `MIN_FRONT_MM`, naming `modules[n].fronts`. Verify: the 800 × 2000 × 400 mm cabinet with the 26° left inside height fold from 1100 mm and two hinged doors is accepted; the same fold with `dividers` 1 is refused naming `modules[0].dividers`; a door pinched below 100 mm is refused naming `modules[0].fronts`.

## 2. Derivation

- [x] 2.1 Add a front-outline helper on `fold_profile` (outer silhouette in the front plane, 1.5 mm inset, vertical splits at equal shares of the unbent width). Rectangular nets stay rectangles; others are n-gons with a grain-aligned bounding rectangle and notes naming the net. When the two doors of one entry have different nets, emit `{id}-door-{entry}-1` and `-2` left to right, each qty 1. Verify the furniture-packages scenario "Two doors follow a left height fold".

- [x] 2.2 Folded adjustable shelves: cut to `min_inner_width` along the board, then the adjustable-shelf clearance, floored. Separate `{id}-adjustable-shelf-{n}` when widths differ. Drawer boxes use `min_inner_width` over the drawer's height, less runner clearance. Verify "Adjustable shelf on a fold uses the pinched width", and that an unfolder module still derives `{id}-door-1` qty 2 and `{id}-adjustable-shelf` as today.

- [x] 2.3 Pin and hinge drilling: name the split side-board ids. Map pin holes and hinge plates onto lower/upper (or front/back) by height; slope-measure holes past the kink from that board's lower end; note plates on the sloped board. Verify the two hardware-drilling scenarios, and that a module with no folds still names `{id}-side`.

## 3. Generator

- [x] 3.1 Draw folded overlay fronts from the outline helper: `_box` when the net is a rectangle, `_prism` in the front plane when it is not, named by the cut-list id, layer `fronts`. Verify with a headless `--blender` test (no render) of the 26° cabinet with two doors and four shelves: the right door is a full-height rectangle, the left door mesh follows the left profile, both are in `spec.layers.fronts`. Verify the existing `--blender` suite still passes.

## 4. Designer and import

- [x] 4.1 `instructions/designer.md`: a folded module may carry overlay fronts and adjustable shelves; fronts follow the folded opening; dividers on a fold are still not expressible; bevels stay unexpressible. Verify `test_the_designer_knows_side_folds` still passes and a new assertion that the text allows fronts and adjustable shelves on a fold and still refuses dividers on a fold.

- [x] 4.2 Update the import template guide: overlay fronts and adjustable shelves follow the folded opening; a folded module cannot carry dividers. Verify the design-import scenarios "Guide names side folds" and "Guide allows fronts on a fold", and that the template still derives the starter's rows.

## 5. Checks and owner test

- [x] 5.1 Run `uv run ruff check .`, `uv run pytest -m "not slow"` and the `--blender` suite in `backend/`. All must pass.

- [x] 5.2 Owner test in the chat on a real carcass that already has doors: "The left side of the carcass should have a 26 degree bend from 1100 mm". The Designer restates the fold, the owner confirms, the revision is accepted with the doors kept, and the headless build's screenshot shows the kink and the doors. One optional `draft` turntable through the guard. Record the owner's verdict in this change.

  First attempt (2026-10-09): the Designer refused a 26° bend on the Murphy bed's left bookshelf as if there were no field for a panel bend. Prompts, the `revise_package` tool description, `side_folds` schema descriptions and a composed Designer note now name `side_folds` as that field. Retest after restarting the backend so it loads the new instructions.

  Done 2026-10-10: the owner marked the chat test complete.
