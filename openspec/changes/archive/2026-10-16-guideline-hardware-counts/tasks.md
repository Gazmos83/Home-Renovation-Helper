## 1. Count checks and rules

- [x] 1.1 In `backend/app/blender/custom_build/derive.py`, add `PIN_COUNT_CHECK = "shelf_pin_count_for_width"`, `HINGE_COUNT_CHECK = "hinge_count_for_height"` and `CALCULATOR_CHECKS` (the bracket checks plus these two), next to `BRACKET_COUNT_CHECK`. Verify that `uv run ruff check .` passes.
- [x] 1.2 In `backend/app/guidelines/checks.py`, add the strict parameter models:
  - `PinCountRow{max_width_mm, pins}` and `PinCount{table, beyond}`;
  - `HingeCountRow{max_height_mm, hinges}` and `HingeCount{table, beyond}`.

  Counts are whole numbers from 1 to 64. Limits are whole millimetres from 1 to 10000. Rows rise strictly, and a validator refuses a non-rising or duplicate limit. Add both checks to `CHECKS` as `piece` checks whose run returns `[]`. Verify with new cases in `tests/test_design_rules.py`:
  - a valid table parses;
  - `"4-5"` and `4.5` are refused naming the rule and `parameters`;
  - a falling table is refused;
  - evaluating a piece with doors and adjustable shelves gives no finding (scenario "No finding from a count rule").
- [x] 1.3 In `backend/app/guidelines/rules.py`, refuse a second rule on any check in `CALCULATOR_CHECKS`, naming both rules. Verify with a test for "Second pin-count rule refused" at load time. Also verify through the panel route in `tests/test_admin_rules*.py` (or the existing rules-API test file) that the rules in force are unchanged afterwards.
- [x] 1.4 Add `shelf-pin-count` and `hinge-count` to `config/design_rules.yaml`. Both are `warn`, cite `owner:7cf8c9ef-e98f-4d3d-af6c-f0384a17ffdd` and `owner:a8147011-0f73-4e5e-a5f2-e3a9f8fd9852`, and quote the notes' clauses. Add comments stating 36 in = 914.4 mm → 914 and "5 or more" → 5. Also update the header's list of checks. Verify with a test for "Shipped rules load": `load_rules()` holds both rules with the stated tables, and `GET /admin/rules` lists them with origin "file".

## 2. Frozen inputs

- [x] 2.1 In `backend/app/guidelines/hardware_inputs.py`, freeze every rule whose check is in `CALCULATOR_CHECKS`, with the same shape as the bracket rules. Verify in `tests/test_hardware_inputs.py` that a frozen spec holds both count rules with their params and source, and that the bracket rules are still frozen as before.

## 3. Derivation

- [x] 3.1 Change `_pin_line` to take the adjustable boards' cut widths and apply this order: sheet `pins_per_shelf` × boards; else the pin-count rule per board width (row or `beyond`), summed; else no quantity. The note names the source. Update the five call sites to pass widths. Verify with new cases in `tests/test_custom_build_generator.py` or `tests/test_drill_shelf_pins.py`:
  - "Pin count from the rule": the Kommode module, 2 × 762 mm boards → 8, and the note names `shelf-pin-count`;
  - "Wide shelf takes the beyond count": 1162 mm → 5;
  - "Data sheet wins over the pin rule": 6 per shelf;
  - "No sheet and no rule": blank;
  - a module with bays of different widths sums per board.

  Also verify that the existing "Adjustable shelves listed" test still passes.
- [x] 3.2 Change `_hinge_count(sheet, height, rule)` to return the count and its source (sheet table, rule, or the `hinges_for_height` fallback). Pass `_rule(inputs, HINGE_COUNT_CHECK)` from `_hinge_lines`, `_hinge_entries` and the plate entries. The hardware note and the drilling entry name the source. Verify in `tests/test_drill_hinges.py` and the derive tests:
  - "Rule decides a 1000 mm door": 2 per door, 4 borings, `hinge-count` named;
  - "Data sheet table wins over the rule";
  - "Version without the rule keeps the fallback": 3;
  - "Hinge count from the rule": 2 × 1550 mm → 8.
- [x] 3.3 Verify that nothing changes when there are no inputs: the existing "Default hinge unchanged" test and the template derivation tests in `tests/test_design_import.py` and `tests/test_custom_build_spec.py` still pass unchanged.
- [x] 3.4 Verify "Frozen rule kept after an edit". Build a version through the packages API (or the service helper the existing frozen-inputs tests use), edit `hinge-count` through the panel route, and check that the first version's derived hardware and drilling list are unchanged while a newly frozen spec holds the edited rule. No render is involved: the test reads the frozen inputs and derives, with no Blender run.

## 4. Wrap-up

- [x] 4.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` in `backend/`, leaving out the RunPod and offload test files. Both must pass.
- [x] 4.2 Run a manual check without rendering. Import the Kommode Harmony document (`kommode-harmony-import.json`) and build its first version. Its hardware must list `shelf-pin` × 8, citing `shelf-pin-count`, and `hinge-concealed-110` × 4, citing `hinge-count`. Building uses the headless generator's blockout and screenshot only, with no turntable, so no render tier applies. Then remove the workshop note on assumed shelf pins from that document, because the rule now covers it. Done (owner's choice, 2026-10-16) as a read-only check instead of an import: the Kommode document was derived with inputs frozen from the real database's rules and data sheets, giving `shelf-pin` × 8 (`shelf-pin-count`) and `hinge-concealed-110` × 4 (`hinge-count`); the note was removed from the document.
