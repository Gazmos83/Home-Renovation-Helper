## 1. Schema and derivation

- [x] 1.1 Add `HandleIn` to `backend/app/blender/schemas.py`. Its fields are `kind`, `length`, `orientation`, `edge`, `inset_mm`, `at_mm`, `finish` (default `black`) and `key`. Add an optional `handle` to `DoorIn`, `DrawerIn` and `FlapIn`. Validators refuse, naming the field:
  - a bar without `length`;
  - `length` or `orientation` on a knob;
  - `edge` on a drawer or flap;
  - a handle on a push-latch door;
  - `edge: meeting` on an odd count.

  Verify with new cases in `tests/test_custom_build_spec.py`.
- [x] 1.2 Add `handle_spec` (defaults resolved once) and `handle_layout(module, t, b)` to `backend/app/blender/custom_build/derive.py`, on top of `front_layout`. Cover:
  - meeting edges paired from the left;
  - the handle edge per front type;
  - the default inset (half the leaf height for drawers);
  - `at_mm` measured along that edge;
  - the default key `handle-bar-<length>-<finish>` / `handle-knob-<finish>`.

  Verify with derive tests for the scenarios "Bar handles on a pair of doors" and "Drawer handles" (centre positions and keys).
- [x] 1.3 Make `CustomBuildSpec._check_fronts` refuse a handle not at least 10 mm inside its leaf (naming `modules[i].fronts[j].handle` and the leaf size), and any `handle` on a module with `side_folds`. Verify with tests for "Handle too long for its leaf" and "Handle on a folded module refused".
- [x] 1.4 In derive, add `handles` to `LAYER_NAMES`. Add `_handle_lines`: one hardware line per key, quantity being the leaves, with the item text "Bar handle <length> mm, <finish>" / "Knob, <finish>" and the note "Rule: one handle per leaf". The door row note reads "; handle <key>" when the entry has a handle. Verify that:
  - derive tests show the lines and notes;
  - the shipped templates and a handle-free fixture derive identical rows and hardware to before.

## 2. Generator

- [x] 2.1 In `backend/app/blender/generators/build_custom_build.py`, draw each `handle_layout` record after the cut-list loop as one `_prism` mesh, named `<front row id>-handle` (`#n`). A bar is 12 × 12 mm, 30 mm proud, on two posts 15 mm in from its ends; a knob is a 16-sided cylinder Ø30 × 25 mm. The mesh:
  - is parented to its module's empty, in layer `handles`;
  - uses material `Handle <finish>` and carries a `hardware_key` property, with no `part_id`.

  Add `brass` to `_COLOURS`. Verify with 2.2.
- [x] 2.2 `--blender` tests in `tests/test_custom_build_generator.py`, each a headless build with Workbench screenshot and views only, no render tier:
  - a two-door module with a meeting-edge 900 mm bar has two handle objects at the expected world bounds, in the `handles` layer of `spec.json`;
  - five drawers with handles give five handle objects;
  - `cutlist.csv` has no handle row and `overall` is unchanged;
  - a handle-free template builds the same object names and layers as before.

## 3. Designer and import

- [x] 3.1 Make `describe_front` in `backend/app/agent/revise.py` append the handle: kind, length, orientation, edge for doors, finish, and the key when it is not the default. Verify with revise tests for the scenarios "Handle added to fronts" and "Handle on a push-latch door refused".
- [x] 3.2 Confirm that the context summary in `backend/app/agent/prompts.py` names handles through `describe_front`. Add a prompts test for "Handles visible". Add one line on `handle` to `backend/app/agent/instructions/designer.md`, saying not to also write a hardware line for a modelled handle. Verify with `tests/test_instructions.py`.
- [x] 3.3 Add a guide line on `handle` to `backend/fixtures/packages/templates/import-template.json` (fields, push-latch rule, one handle per entry, no duplicate hardware line, projection not in the overall size). Keep the guide within 40 notes of at most 500 characters. Verify that `tests/test_design_import.py` passes the "Guide names handles" check and that the template is still valid as shipped.

## 4. Checks

- [x] 4.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` in `backend/`, skipping the RunPod/offload test files. Then run the `--blender` suite for the custom-build generator tests. All must pass.
- [x] 4.2 Browser pass: import `amesbury-wardrobe` v2 with handles on all fronts and its hand-written handle lines removed, using `import_design_version`. The headless build makes Workbench screenshots only, no render tier. In the inspector, check that:
  - handles show in Workshop view;
  - a `handles` layer switch appears and hides them;
  - the exploded view moves them with their modules;
  - the cut list has no handle rows and the hardware lists the handle keys.
