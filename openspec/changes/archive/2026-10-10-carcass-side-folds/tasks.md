## 1. Schema

- [x] 1.1 Add `SideFoldIn` (`side`, `from_mm`, `along`, `angle_deg`, `towards`) and optional `side_folds` (max 2) on `ModuleIn`, omitting the field when empty. Verify with schema tests: the 800 × 2000 × 400 mm `cabinet` fold from the furniture-packages scenario is accepted; two folds on the same side, `from_mm` inside the carcass thickness, a 0 mm inset, a pinch below 1 mm inner width, fronts, dividers and adjustable shelves on a folded module are each refused naming the field path in that scenario.

- [x] 1.2 Add `side_folds` to `ModuleChange` (`[]` clears). Switch envelope fit and `_boxes_overlap` to the folded bounding box from `derive.module_bounds`. Verify a `PackageChanges` test accepts `{"modules": {"cabinet": {"side_folds": [{"side": "left", "from_mm": 1100, "along": "height", "angle_deg": 26, "towards": "inside"}]}}}` and refuses `"bevel_mm"` by name; an `outside` fold that leaves the envelope is refused naming the module.

## 2. Derivation

- [x] 2.1 Add `inset_mm`, `fold_profile` and `module_bounds` to `custom_build/derive.py` (shared rounding: nearest millimetre, halves away from zero). Verify 900 mm at 26° → inset 439 mm and along-slope length 1001 mm; an inside left height fold on the 800 × 2000 × 400 mm 18/12 mm cabinet → overall width 800 mm; the same fold `towards: outside` → overall width 1239 mm.

- [x] 2.2 Rework `_module_rows` and assembly: split side rows, separate top/bottom when sizes differ, mitre notes, confirmat 8 + 4 per fold joint + 4 per fixed shelf board, an assembly step naming the side, angle and `from_mm`. Update the module docstring's rule table. Verify the furniture-packages scenario "Left side 26 degrees from 1100 mm" (confirmat 12, 1100 × 388 and 1001 × 388 left pieces, 2000 × 388 right), that `[]` after a fold restores `{id}-side` quantity 2, and that every shipped template and fixture still derives row-for-row.

## 3. Generator

- [x] 3.1 Draw folded modules from `fold_profile`: two side boxes with the upper or rear board rotated by `angle_deg`, remaining rectangular parts from the profile, the back as an n-gon in the back plane named by its cut-list id. Dimension lines use `module_bounds`. Verify with a headless `--blender` test (no render) of the 26° left height-fold fixture: lower and upper left-side objects meet at 1100 mm within 0.1 mm, the upper board is 26° to vertical within 0.1°, the right side is a full-height box, and `spec.layers` lists the new carcass and back ids. Verify the existing `--blender` suite still passes.

## 4. Guidelines, pricing, import

- [x] 4.1 Make `guidelines/checks.shelf_span` use the widest shelf cut width on a folded module. Verify the design-guidelines scenario "Outside fold widens the span", and that inside folds and modules without folds still use the unbent inner width.

- [x] 4.2 Verify a priced version whose cut list includes a side-upper row with notes naming a 26° mitre marks that row for review (`cut-list-pricing` scenario "Derived mitre notes marked for review"). The existing keyword list already includes `mitre`; add a derivation-to-pricing test if none covers a derived note.

- [x] 4.3 Add a guide line to `import-template.json` describing `side_folds` and the folded-module refusals. Verify the design-import scenario "Guide names side folds" and that the template still derives the starter's rows.

## 5. Revision and Designer

- [x] 5.1 `revise._apply_module_change`: setting `side_folds` replaces the list; `[]` clears it, with change lines that name each fold (side, from_mm, along, angle, towards). Verify the furniture-packages scenario "Folds cleared in a revision".

- [x] 5.2 `measurements`: treat `side_folds` as an optional list field compared by each fold's `from_mm`. Verify the three design-agents scenarios under "Requested side-fold measurements are checked".

- [x] 5.3 Piece summary in `prompts.py`: "left side fold from 1100 mm along height, 26°, inside". Verify `test_piece_note.py` for the design-agents scenario "Side fold visible".

- [x] 5.4 `instructions/designer.md`: describe `side_folds`, give the owner's sentence as the worked example, restate `along: height` and `towards: inside` when the owner omits them, and keep bevels as unexpressible. Verify `test_the_designer_knows_shelf_spacing_and_dividers` still passes and a new assertion that the text names `side_folds`, `from_mm`, `along`, `angle_deg` and `towards`.

## 6. Checks and owner test

- [x] 6.1 Run `uv run ruff check .`, `uv run pytest -m "not slow"` and the `--blender` suite in `backend/`. All must pass.

- [x] 6.2 Owner test in the chat on a real carcass: "The left side of the carcass should have a 26 degree bend from 1100 mm". The Designer restates the fold (along height, towards inside if omitted), the owner confirms, and the headless build's screenshot shows the kink. One optional `draft` turntable through the guard. Record the owner's verdict in this change.

   Owner verdict (2026-10-09): the fold itself is wanted, but the v1 refusal of fronts, dividers and adjustable shelves on a folded module blocks a real carcass (the starter already has doors). Non-rectangular builds must be able to carry shelves and doors. Open a separate change for that; this change keeps the v1 refusals as specified.
