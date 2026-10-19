## 1. Schema and derivation

- [x] 1.1 In `backend/app/blender/schemas.py`, add `SlatsIn` with these fields:
  - `count` 1–40;
  - `width`;
  - `material` (a slot);
  - `orientation` (`vertical` or `horizontal`; default vertical, omitted when unstated);
  - `margin_mm` 0–500;
  - `leaves`.

  Add an optional `slats` to `DoorIn`. Refuse, naming the field:
  - a `leaves` number outside `count`, or a repeated one;
  - an undefined `slats.material` slot (in `CustomBuildSpec`);
  - `slats` on a module with `side_folds`.

  Verify with new cases in `tests/test_custom_build_spec.py`, including "Slats on a drawer refused" (unknown field) and "Leaf outside the count refused".
- [x] 1.2 Add `slat_layout(module, materials, t, b)` to `backend/app/blender/custom_build/derive.py`, using the spacing rule in design.md §3 for both orientations. It refuses a gap under 3 mm (naming the leaf's size across the slats and the largest count that fits) and a margin that leaves no room. Call it from `CustomBuildSpec._check_fronts`. Verify with derive tests for:
  - "Vertical slats on the right door only" (positions, 22.4 mm gap);
  - "Horizontal slats";
  - "Margin";
  - a single centred slat;
  - "Too many slats refused" (at most 12).
- [x] 1.3 In `_add_front_rows`, add one `<door row id>-slat` row ("Door slat", count × slatted leaves, slot material and thickness, grain by orientation, the note from design.md §4). Verify with derive tests for:
  - "Slats on both doors by default" (×12);
  - "Slats follow a resized door";
  - "Fewer slats re-spaces them";
  - the shipped templates and a slat-free fixture, which must derive identical rows and hardware to before.
- [x] 1.4 Add `slat_handle_warnings(spec)` to derive, and append each warning to its slat row's note as " Warning: …". Verify with derive tests for "Warning in the cut list" (the knob or bar on door 2 only, and the exact sentence) and "No handle, no warning".

## 2. Generator

- [x] 2.1 In `backend/app/blender/generators/build_custom_build.py`:
  - add the slat boxes from `slat_layout` to `pieces` under `<row>-slat` in the `fronts` layer, `t + slat_t/2` in front of the module's front plane, in leaf-then-position order;
  - move a slatted leaf's handle out by the slat thickness in `_handle_pieces`;
  - add `anthracite` and `anthrazit` to `_COLOURS` before `black`.

  Verify with 2.2.
- [x] 2.2 Add `--blender` tests in `tests/test_custom_build_generator.py`. Each is a headless build with Workbench screenshots and views only, **no render tier**:
  - vertical slats on door 2 give `kommode-door-1-slat` … `#8` at the expected world bounds, in the `fronts` layer, parented to the module;
  - horizontal slats run across the door, ordered top to bottom;
  - a knob on a slatted leaf has its front face 25 mm in front of the slats' face, and the plain leaf's knob 25 mm in front of the door;
  - `cutlist.csv` equals the derived cut list, including the warning note, and `overall` is unchanged;
  - a slat-free template builds the same object names and layers as before;
  - a slot named "anthracite …" gets the dark colour.

## 3. Designer, previews and import

- [x] 3.1 In `backend/app/agent/revise.py`, make `describe_front` append the slat phrase (count, orientation, width, margin when not 0, and doors when `leaves` is set). After the derived changes, the revision confirmation lists the revised document's slat-handle warnings. Verify with revise tests for "Slats added to a door", "Slat count changed" and "Handle over slats warned before confirming".
- [x] 3.2 In `backend/app/agent/prompts.py`, have the active-build summary name the slats through `describe_front` and add a "Warnings:" line for the slat-handle warnings. Add one line on `slats` to `backend/app/agent/instructions/designer.md`. It covers:
  - the fields;
  - that slats follow the door, so the count is the style control;
  - that slats are not written as extra parts;
  - the warning when a handle sits on slats.

  Verify with prompts tests for "Slats visible" and "Slat-handle warning visible", and with `tests/test_instructions.py`.
- [x] 3.3 In `backend/plugins/create_piece/tool.py` (`summarise`) and `backend/plugins/design_import/tool.py` (both previews), append "Slat-handle warnings: …" after the design-rule warnings when there are any. Verify with tool tests for "Warning in an import preview" / "Slat-handle warning in the preview", and a create-piece preview with and without the warning.
- [x] 3.4 Add a guide line on `slats` to `backend/fixtures/packages/templates/import-template.json`. It covers:
  - the fields;
  - vertical or horizontal;
  - that slats follow the door;
  - that they are cut parts, not extra parts;
  - the handle warning.

  (The note that their thickness is outside the overall size was dropped to keep the line within 500 characters.)

  Keep the guide within 40 notes of at most 500 characters. Verify that `tests/test_design_import.py` passes "Guide names slats" and that the template is still valid as shipped.

## 4. Checks

- [x] 4.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` in `backend/`, skipping the RunPod/offload test files and using a throwaway `TEST_DATABASE_URL` if another session holds the test database. Then run the `--blender` suite for the custom-build generator tests. All must pass.
- [x] 4.2 Browser pass. Import a copy of the Höffner "Kommode Harmony" with `import_design_version`: two hinged doors, 8 vertical oak slats on door 2, and black knobs. The headless build makes Workbench screenshots only, **no render tier**. Check that:
  - the import preview shows the slat-handle warning for door 2 only;
  - in the inspector, the slats show on the right door in Workshop view, hide with the `fronts` layer switch, and move with the module in the exploded view;
  - the cut-list table lists `…-slat` ×8 with the warning in its note;
  - after a revision to 5 horizontal slats, the confirmation shows the new slat phrase and the warning, and the new version's slats run across the door.
- [x] 4.3 Optionally queue a **draft**-tier turntable of that version through the render guard (owner approval as usual) to see the slats lit. No `final` tier.
