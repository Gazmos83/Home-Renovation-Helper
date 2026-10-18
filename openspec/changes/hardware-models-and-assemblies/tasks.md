## 0. Precondition

- [ ] 0.1 Confirm `hardware-catalog` is applied and archived. Its pytest files were written but not run there, so run them first and fix any failure in that change's code before starting: `tests/test_hardware_catalog.py`, `tests/test_import_corrections.py`, and the new cases in `test_custom_build_spec.py`, `test_design_rules.py`, `test_design_import.py` and `test_instructions.py`. Then record a green baseline: `uv run pytest -m "not slow"` on a throwaway `TEST_DATABASE_URL`, RunPod and offload files left out, plus the `--blender` suite.

## 1. Library models for hardware keys

- [ ] 1.1 Add the `hardware_models` table (key → model id) with an Alembic migration. Add owner-gated assign and clear routes refusing a model that is not ready, an unknown key, or a size outside the tolerance. Verify with "Assigned", "Size too far off" and "Not ready" in a new `tests/test_hardware_models.py`.
- [ ] 1.2 Freeze the assignments with the version's hardware inputs, and pass the assigned model paths to the runner. Extend CLAUDE.md §8's sentence on headless generators. Verify that a frozen spec holds the assignment and that reassigning later leaves it unchanged.
- [ ] 1.3 In `build_custom_build.py`, import each assigned file once into a hidden collection and instance it at each record, anchored by the shape's mounting face at the stated size. Verify with `--blender` tests "Knob model used" and "Model removed", using a small fixture GLB.
- [ ] 1.4 On the model library page, add assigning, clearing, the convention text and the keys listed. Verify with Vitest and a recorded browser check ("Assign from the page").

## 2. Assemblies and the fold-down bed

- [ ] 2.1 Add assembly entries to `hardware_catalog.py` (components, parents, pivots, pose angles and limits) and `fold-bed-vertical` to `config/hardware.yaml`. Verify "Assembly loads" and "Cycle refused".
- [ ] 2.2 Add `FoldBedIn` and `fold_bed` to `schemas.py` and `ModuleChanges`/build changes, with the refusals. Verify "Mattress too big", the floor refusal, and a document without `fold_bed` serialising as before.
- [ ] 2.3 Add the assembly layout in `derive.py`: cut-list rows in module `fold-bed`, illustrative hardware lines, and the build note. Add wording in `revise.py` and `prompts.py`, and `fold_bed` in `designer.md`. Verify "Components listed and drawn" (rows and lines), and a revise change line.
- [ ] 2.4 Draw the components in a `mechanism` layer, one object per component id, in the stored pose. Verify with a `--blender` test on murphy-bed with a 1600 × 2000 mm `fold_bed`.

## 3. Poses

- [ ] 3.1 Export the other pose as `model-open.glb` / `model-closed.glb`, list `poses` and `pose` in `spec.json`, and report export times in the status. Verify "Both poses written". Also verify "Time limit": the second export adds no more than 90 s on murphy-bed, measured on the laptop with a blockout build and no render, so no tier applies.
- [ ] 3.2 Add the inspector's Folded / Unfolded switch, loading the pose file on demand. Verify "Unfolded" and "No switch" with Vitest, and a recorded browser check.
- [ ] 3.3 Add an optional `pose` to the render tools, refused unless it is in `poses`, and applied in memory. Verify "Unknown pose" and that the guard still interrupts on `final`, in the render-guard tests. Verify "Open pose draft" with one `draft` turntable through the guard. Tier: `draft`.

## 4. Import

- [ ] 4.1 Add the mechanism warning to `import_corrections.py` and `fold_bed` to the template guide. Verify "Murphy mechanism warned" and "Template valid as shipped".

## 5. Wrap-up

- [ ] 5.1 Run `uv run ruff check .`, `uv run pytest -m "not slow"` (throwaway test database, RunPod and offload files left out), the `--blender` suite, and `pnpm lint`, `pnpm test` and `pnpm build`. All must pass.
