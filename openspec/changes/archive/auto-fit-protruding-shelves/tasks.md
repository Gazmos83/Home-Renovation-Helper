## 1. Fit step

- [x] 1.1 In `app/agent/revise.py`, add the fit after the module changes: compute the overhang from `module_bounds` per module, raise every module and wall-shelf `y` and the envelope depth by the largest, and add the lines (module, old → new y; envelope depth old → new; the causing shelf). Verify unit tests: 400 mm cabinet, shelf 550 back-aligned → y 162, envelope 562; a two-module row moves together; no protrusion leaves the document equal; no envelope adds none.
- [x] 1.2 Verify the fitted document passes `CustomBuildSpec` and that a still-invalid change (module wider than the envelope) is refused unchanged. Test both.

## 2. Confirmation and the measurement check

- [x] 2.1 In `plugins/revise_package/tool.py` keep the fit lines in the confirmation summary after the owner's lines. Verify a preview test shows `y 0 → 162` and `400 → 562`.
- [x] 2.2 Verify the requested-measurement check accepts a revision with only the shelf depth stated (`measurements.check` test); change code only if it refuses.

## 3. Decisions row

- [x] 3.1 In `revise_package.run`, after the version is created, append one row through `decisions_note.append_row` and `store_note` when the revision carried a fit. Verify tests: confirmed → row text contains shelf, overhang and envelope change; declined, refused and no-fit → note unchanged.
- [x] 3.2 Verify a failing row write does not undo the created version, and report whether the append marks the note owner-edited the way `edit_decisions` does.

## 4. Designer and room

- [x] 4.1 Edit `app/agent/instructions/designer.md` (and the shelf-depth note in `prompts.py` if it repeats the claim) to say the app fits position and envelope for a protruding shelf and never to propose deepening the module for one shelf. Verify `tests/test_instructions.py` asserts the wording.
- [x] 4.2 Verify a `room_fit` placement of a fitted piece still passes, using the 400/550 fixture.

## 5. Close

- [x] 5.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` (one pytest process) and the `--blender` suite for the `shelf_depths` fixture; all pass.
- [ ] 5.2 Browser pass: in the studio chat ask for a 550 mm second shelf on a 400 mm cabinet; confirm the confirmation text, the new version, and the decisions row.

## 6. Folded modules

- [x] 6.1 In `schemas._check_shelf_depths`, accept a `"back"`-aligned depth above the folded inner depth and refuse only a `"front"`-aligned one, naming `modules[n].shelf_depths_mm`. Verify tests: 400 mm cabinet, left fold from 1100 mm along height at 26°, `[null, 550, null]` back-aligned is accepted; the same with `"front"` is refused naming the field and 388 mm.
- [x] 6.2 In `derive.py` and `build_custom_build.py`, cut and draw a protruding board on a folded module at the width the fold allows over its inside part. Verify a derive test (shelf row width at its height, bounds include the protrusion), a fold along depth as well as along height, and a `--blender` build of the 400/550 folded fixture whose shelf object depth and centre match the derived placement within 0.1 mm.
- [x] 6.3 Verify that revising the fitted folded fixture keeps the fold, applies the fit (`y` 162, envelope 562) and passes `CustomBuildSpec` in one `revise_spec` test.

## 7. Fold guard

- [x] 7.1 In `measurements.py` and the `revise_package` tool, refuse a `side_folds` set, change or clear without a matching `requested` entry whose quote is in the owner's messages since the last version and names a fold; the refusal names `side_folds` and the module and tells the Designer to ask. Verify tests: the three scenarios of the design-agents delta (cleared without a request refused, changed on request confirmed, untouched fold needs no entry), each asserting that no version is created on refusal.
- [x] 7.2 In `designer.md` and the shelf-depth note in `prompts.py`, say that a fold is never cleared or changed to satisfy another rule and that a refusal about a fold is relayed to the owner. Verify `tests/test_instructions.py` asserts the wording.
- [x] 7.3 Re-run `uv run ruff check .`, `uv run pytest -m "not slow"` (one process) and the `--blender` suite; all pass except any failure shown to predate this change.
