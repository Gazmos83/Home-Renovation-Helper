## 1. Schema

- [x] 1.1 Add `shelf_spacing_mm`, `shelf_positions_mm`, `dividers` and `divider_positions_mm` to `ModuleIn`, with the refusals from the furniture-packages delta (both shelf fields, positions without shelves or dividers, wrong count, not increasing by a board thickness, shelf above the top panel with the inner height named, divider outside the inner width, bay ≤ 0). Verify with new cases in the schema tests, each asserting the field path named in the refusal.
- [x] 1.2 Add the four fields to `ModuleChange`, where `0` / `[]` means clear. Verify that a `PackageChanges` test accepts `{"modules": {"cabinet": {"shelf_spacing_mm": 355}}}` and refuses `"divider_material"` by name.

## 2. Derivation

- [x] 2.1 Add the shared `interior(module, t, b)` helper to `custom_build/derive.py` (bay ranges, shelf underside heights, lowest first, fixed before adjustable). Verify with unit tests: 1600 mm module, 4 shelves, 355 spacing → 355/728/1101/1474. 1000 mm wide, 2 dividers → bays 309. 1 divider at 400 → bays 400 and 546.
- [x] 2.2 Rework `_module_rows`: a divider row; shelf rows per bay width (the same id when bays are equal, `-bay-<n>` when unequal); confirmat 8 + 4 × fixed boards + 4 × dividers; pins × adjustable boards. Update the module docstring's rule table. Verify the scenarios "Two dividers, equal bays" and "Positioned divider, unequal bays", and that every shipped template and fixture derives row-for-row as before (snapshot test).
- [x] 2.3 Extend `_shelf_pin_entries` with a divider entry (both faces, same heights, its own count). Verify the hardware-drilling scenarios "Holes on a divider listed" and "No dividers, unchanged".

## 3. Generator

- [x] 3.1 Make `build_custom_build._module_boxes` place shelves from `rules.interior` when spacing, positions or dividers are stated, and draw `<id>-divider` boxes in the `carcass` layer. Keep the current float step when none is stated. Verify with a headless `--blender` test build (no render) of a fixture with 2 dividers and 4 shelves 355 apart: 2 divider objects, 12 shelf objects, undersides at the calculated heights within 0.1 mm. Verify also that the existing `--blender` suite passes unchanged.
- [x] 3.2 Confirm the version's `spec.layers` lists the divider and per-bay shelf ids, so the inspector's layer switches cover them. Verify with an assertion in the same `--blender` test.

## 4. Guidelines

- [x] 4.1 Make `guidelines/checks.shelf_span` measure the widest bay and name it. Verify the design-guidelines scenarios in the checks tests.

## 5. Revision and Designer

- [x] 5.1 `revise._apply_module_change`: setting spacing drops positions and vice versa, with change lines; `0` / `[]` clears. Verify with the scenario "Spacing set in a revision" in the revise tests.
- [x] 5.2 `measurements`: accept an absolute length on an unset module field, refuse a relative one naming the field, and match list fields by membership. Verify the three scenarios in "Requested shelf and divider measurements are checked" in the measurements tests, with all existing measurement tests still passing.
- [x] 5.3 Piece summary in `prompts.py`: "4 shelves 355 mm apart", "shelves at [300, 700, 1300] mm", "2 dividers (equal bays)" / "1 divider at [400] mm". Verify the scenario "Spacing and dividers visible".
- [x] 5.4 `instructions/designer.md`: describe the four fields, prefer `shelf_spacing_mm` for "X apart", never compute heights from a spacing, and give one example each. Verify that the prompt-loading test still passes and that the text names all four fields.

## 6. Checks and owner test

- [x] 6.1 Run `uv run ruff check .`, `uv run pytest -m "not slow"` and the `--blender` suite in `backend/`. All must pass.
- [x] 6.2 Owner test in the chat on a real piece: "4 shelves 355 mm apart", then "add 2 vertical dividers", then "move the divider to 400 mm from the left". Each is a headless build with a blockout screenshot, plus one optional `draft` turntable through the guard. Record the owner's verdict in this change. If it is not good enough, open a separate change to revisit the spec-only rule before the deferred app-check items.

   Owner verdict (2026-10-09): the test worked. The spec-only rule stays.
