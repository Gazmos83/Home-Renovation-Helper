## 0. Precondition

- [x] 0.1 Confirm `guideline-hardware-counts` is committed and archived, so its furniture-packages text is the base of this change's delta. The pytest suite is not run in this change (owner's decision 2026-10-16); it runs in `hardware-models-and-assemblies` 0.1 and 5.1.

## 1. Catalog

- [x] 1.1 Add `backend/app/blender/hardware_catalog.py`, with strict models per shape, the finish set, the key/pattern lookup (exact key, then the longest pattern prefix), and `load_catalog()` refusing by file and entry. Verify with new `tests/test_hardware_catalog.py`: "Catalog loads", "Unknown shape stops startup", "Wrong size field", a duplicate key, and the pattern precedence.
- [x] 1.2 Add `backend/config/hardware.yaml` with the default rule keys, the handle patterns, `rail-oval-30x15` and `rail-support-oval`. A header comment says the sizes are typical catalogue sizes, not engineering values (TODO(user) to confirm). Load it in the app lifespan beside the design rules. Verify with a startup test that a broken file stops startup naming it.

## 2. Hanging rails

- [x] 2.1 Add `HangingRailIn` and `hanging_rails` (at most 4) on modules and in `ModuleChanges` in `schemas.py`. Add the refusals: no bay, rail through a shelf or divider, too close to the board above, folded module, missing `z`. Verify with cases in `tests/test_hardware_layout.py` (kept with the other rail cases rather than in `test_custom_build_spec.py`): "Rail through a shelf refused", "Missing height refused", and a document without rails serialising as before.
- [x] 2.2 Add `rail_support_count_for_length` to `checks.py` (count check, judges nothing), the one-rule limit in `rules.py`, and freezing in `hardware_inputs.py`. Ship no rule. Verify with "Supports from the rule", "No rule, end supports only" and "Second rail-support rule refused".
- [x] 2.3 In `derive.py`, add the rail lines (cut length, item text) and support lines. Wording goes in `revise.py`, and the context summary in `prompts.py`. Verify with "Rail in a wardrobe bay" (lines and quantities), and with a revise change-line test for a rail added.

## 3. Layout and `shown`

- [x] 3.1 Add `derive.hardware_layout(spec, inputs)`, giving records for hinges and shelf pins (exact drilling positions only), drawer runner pairs, owner-stated brackets, and rails and supports. Add `shown` to every hardware row. Verify with derive tests:
  - "Hinges drawn" (positions and `shown` 4);
  - "Pins drawn at exact holes";
  - "Ranged position not drawn";
  - "Free line not drawn";
  - "Confirmat never drawn";
  - the shipped templates deriving the same parts and hardware as before apart from `shown`.

  These are in the new `tests/test_hardware_layout.py`: `test_custom_build_generator.py` is wholly Blender-marked, so derive-only cases there would be skipped without `--blender`.
- [x] 3.2 Add `shown` to `SpecHardware` in `frontend/src/lib/api.ts` as an optional field.

## 4. Generator

- [x] 4.1 In `build_custom_build.py`, add the `hardware` layer and draw every `hardware_layout` record:
  - one object `<line id>#<n>` per piece, sharing a mesh per line;
  - a Bevel modifier, with the curved faces smoothed per face (the Smooth by Angle modifier is a node-group asset that a headless build cannot add without an operator, so it is not used);
  - `Hardware <finish>` Principled materials looked up by node type;
  - `hardware_key` set, with no `part_id`;
  - parented to the module's empty.

  Verify with `--blender` build tests on a module with doors, adjustable shelves, a drawer and a rail: object names, layer map, materials metallic, and the count of drawn objects equal to the sum of `shown`.
- [x] 4.2 Measure the build time of murphy-bed v7 and amesbury-wardrobe v5, rebuilt from their designs in a scratch folder (no render: blockout and screenshot only, so no tier applies). Each must stay under 15 s, and `model.glb` under 2 MB. Record the figures in this task.
  - Measured 2026-10-16: murphy-bed v7 2.3 s, `model.glb` 137 KB; amesbury-wardrobe v5 2.9 s, 391 KB. Neither has hinge or shelf-pin data sheets, so only their runners and handles are drawn.

## 5. Import corrections

- [x] 5.1 Add `backend/app/blender/import_corrections.py`, `correct(document, derived_hardware, catalog)`, giving the corrected document plus removals and warnings, as set out in the design-import delta. Verify with new `tests/test_import_corrections.py`:
  - "Duplicate hinges removed";
  - "Same id not added twice";
  - "Knob line warned, not converted";
  - "Unknown item kept";
  - a hinge line on a design without doors kept with its warning.
- [x] 5.2 Call it from `preview` and `version_preview` in `plugins/design_import/tool.py`. List "Hardware corrections" in the preview, and store the corrected document on yes. Verify in `tests/test_design_import.py`:
  - the murphy-bed v7 design previews the removal of `cabinet-hinges` (×8, counted by rule as `hinge-concealed-110` ×24). Its `shelf-pins` line is kept with a warning, because its shelves are fixed and no rule counts pins for it (checked against the real design 2026-10-16);
  - the stored input lacks the removed line;
  - "Missing quantity still refused".

  The tool-level cases are in `tests/test_import_design.py`, the template's preview and the stored `input.json`. The murphy-bed wording is in `tests/test_import_corrections.py`, and "Missing quantity still refused" is in `tests/test_design_import.py`.
- [x] 5.3 Update `import-template.json`'s guide with the three new bullets, and `designer.md` with `hanging_rails` and the corrections wording. Verify with "Template valid as shipped", "Guide names rule-counted hardware" and `tests/test_instructions.py`.

## 6. Cut list marker

- [x] 6.1 In `CutListTables.tsx`, add the `*`, "(n of m shown)" and the legend. Verify with Vitest cases in `CutListTables.test.tsx`: "Unshown line marked", "Partly shown", "Fully shown, no mark" and "Older version".
- [x] 6.2 Recorded browser check: rebuild murphy-bed as a new version (blockout and screenshot only, no render tier). Open its inspector, switch `hardware` on and off, and check the `*` rows and the legend in the Cut list tab.
  - Passed by the owner's browser check, 2026-10-16.

## 7. Wrap-up

- [x] 7.1 Run `uv run ruff check .` and the `--blender` suite in `backend/`, and `pnpm lint`, `pnpm test` and `pnpm build` in `frontend/`. All must pass. The new pytest files are written here but run in `hardware-models-and-assemblies` (owner's decision 2026-10-16).
  - Run 2026-10-16: `ruff` clean. `--blender` suite: 61 passed (8 min 39 s) over the generator, template, divider, fold, shelf, composition, restyle, turntable, model-check, room and shell files. `test_benchmark.py` and `test_chat_blender.py` were left out because they use the shared test database, and `test_offload_bundle.py` under the RunPod rule. Frontend: `pnpm lint` clean, `pnpm test` 481 passed, `pnpm build` built.
- [x] 7.2 Draft render check: one `draft` turntable of the rebuilt murphy-bed through the render guard. Check that the hinges, pins and metal finishes read correctly. Tier: `draft`.
  - Marked complete by the owner, 2026-10-17.

## Note (2026-10-16)

The full pytest suite ran during `room-render-notices` 4.1, so these files were tested a step earlier than planned. It found and fixed:
- a top-level `import bmesh` in the generator (now imported inside `_draw_hardware`);
- two template guide lines over the 500-character limit (split into four lines);
- two wrong values in the new tests.

`hardware-models-and-assemblies` 0.1 still re-runs them.

