## 1. Schema

- [x] 1.1 Add `shelf_depths_mm` (`list[Millimetres | None]`) and `shelf_depth_align` (`"back" | "front"`) to `ModuleIn`, with the refusals from the furniture-packages delta (wrong length, no shelves, depth below 50 mm, align without depths, envelope overflow, fold inner-depth overflow). Omit both on serialize when unset; omit empty folds-style. Verify new schema tests assert the field path named in each refusal.
- [x] 1.2 Add both fields to `ModuleChange` (`[]` clears depths and align). Verify a `PackageChanges` test accepts `{"modules": {"cabinet": {"shelf_depths_mm": [null, 500, null, null], "shelf_depth_align": "back"}}}` and that clearing depths drops the align.

## 2. Derivation and bounds

- [x] 2.1 Extend `ShelfBoard` with `depth` and `y0`; add helpers for resolved depth and y-placement from align. Update `shelf_boards` / `shelf_rows` to group by (cut width, depth). Verify unit tests: 400 mm module, 12 mm back, depths `[null, 500, null, null]` back-flush → shelf 2 depth 500 and `y0 = 388 - 500`; others depth 388.
- [x] 2.2 Cut-list rows use each board's depth as `w`; notes name the depth when it differs from the back-reduced default. Update the derive docstring rule table. Verify mixed-depth rows become `-shelf-1` / `-shelf-2` (or equivalent numbering) and that every shipped template without the fields derives row-for-row as before.
- [x] 2.3 Expand `module_bounds` / overlap boxes to include protruding shelf AABBs so `overall.d` grows. Verify the furniture-packages scenario "Protruding shelf grows overall depth".
- [x] 2.4 When hardware inputs give exact front and rear setbacks, refuse an adjustable shelf whose placed board misses a pin column (`shelf_covers_pin_columns`). Verify the hardware-drilling scenarios (370 mm accepted, 300 mm refused on a 400 mm module with 37/37 setbacks, back-flush).

## 3. Generator

- [x] 3.1 Place each shelf box from `ShelfBoard.depth` and `y0` in both the rectangular and divider-layout / folded paths in `build_custom_build.py`. Verify a headless `--blender` build (no render) of a fixture with one deeper back-flush shelf: object depth and centre within 0.1 mm of the derived placement, and the existing `--blender` suite still passes.

## 4. Revision and Designer

- [x] 4.1 `revise._apply_module_change`: set/clear depths and align; clearing depths clears align; change lines name both. Verify the scenario "Depths cleared in a revision".
- [x] 4.2 `measurements`: add `shelf_depths_mm` to `LIST_FIELDS` / `OPTIONAL_FIELDS`; membership matches a non-null entry. Verify "One shelf depth covered".
- [x] 4.3 Piece summary in `prompts.py` shows per-shelf depths and align when set. Verify "Per-shelf depths visible".
- [x] 4.4 `instructions/designer.md` plus a short every-turn note (side_folds pattern): name both fields, give the second-shelf-500 example, never claim there is no per-shelf depth field, never deepen the whole module when one shelf was asked for. Verify a prompt-loading / instructions test names the fields.
- [x] 4.5 Import template guide lists `shelf_depths_mm` and `shelf_depth_align`. Verify the design-import scenario "Guide names per-shelf depths".

## 5. Checks and owner test

- [x] 5.1 Run `uv run ruff check .`, `uv run pytest -m "not slow"` and the `--blender` suite in `backend/`. All must pass.
  - ruff clean; related unit tests 299 passed; `pytest --blender -m blender` 58 passed; `pytest -m "not slow"` 2485 passed / 41 skipped / 26 deselected with one unrelated flaky kitchen seed (`test_seed_links_registers_kitchen_sources_without_chunks`, passes alone; not from this change).
- [x] 5.2 Owner test in chat on a real piece: "second shelf from the bottom 500 mm deep, rest at the module depth" (back-flush), then optionally a front-flush shallower top shelf. Each is a headless build with a blockout screenshot. Leave unchecked until the owner confirms; record the verdict here.
