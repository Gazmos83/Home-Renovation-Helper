## 1. Schema

- [x] 1.1 Add `DoorIn.leaf_materials` (`dict` of door-number keys to `SlotName`, optional, omitted when unset) to `backend/app/blender/schemas.py`. It needs:
  - the key and count validator;
  - the slot, thickness and folded-module checks in `_check_fronts`.

  Verify with `tests/test_custom_build_spec.py` for:
  - door outside the count;
  - unknown slot;
  - thickness mismatch;
  - folded module;
  - `leaf_materials` on a drawer refused as an unknown field;
  - a spec without it serialising unchanged.

## 2. Derivation

- [x] 2.1 Add `leaf_material` and `door_row_ids` to `backend/app/blender/custom_build/derive.py`. Use them in `_add_front_rows`, which then splits rows only when materials differ and gives hinges per split row. Verify with spec tests for:
  - "Black right door, oak left door, side by side" (row ids, materials, sizes, hinge totals equal to the pair's);
  - "Same material everywhere keeps one row";
  - "Override of the former pair row refused".
- [x] 2.2 Make `handle_layout`, `slat_layout`, `_add_slat_rows`, the drilling list and `slat_handle_warnings` use the door's row id. Verify with:
  - "Slats on the black door" (`kommode-door-1-2-slat` ×8);
  - a handle on a split door whose drilling-list entry names its own row;
  - the existing slat and handle tests unchanged for unsplit entries.

## 3. Generator

- [x] 3.1 In `backend/app/blender/generators/build_custom_build.py`, `_add_front_boxes` groups door and slat pieces by row. Verify with `tests/test_custom_build_generator.py` (fake path): the split rows' pieces match their qty, the boxes keep their positions, and an unsplit spec's pieces are unchanged.
- [x] 3.2 Verify with the `--blender` suite on Blender 5.2.1, no render (build and inspect only, no render tier):
  - objects `kommode-door-1-1` and `kommode-door-1-2` exist side by side;
  - door 2 uses a black material colour;
  - the slats sit in front of door 2.

## 4. Words and confirmation

- [x] 4.1 `describe_front` names "door <n> <slot>" in `backend/app/agent/revise.py`. Verify with `tests/test_revise.py`, `tests/test_piece_note.py` and an import preview test ("Imported design with a black right door").
- [x] 4.2 Add `front_layout_change` and its line in the revise confirmation. Verify with `tests/test_revise_package.py` for:
  - "Pair split into stacked entries" (line present);
  - "One door's material changed" (no line);
  - a handle-only change (no line).

## 5. Instruction and template

- [x] 5.1 Add the `leaf_materials` line to `backend/app/agent/instructions/designer.md`, and a guide line of at most 500 characters to `backend/fixtures/packages/templates/import-template.json`. Verify with `tests/test_instructions.py` and `tests/test_design_import.py` ("Guide line present").

## 6. Checks

- [x] 6.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` in `backend/`, skipping the RunPod/offload test files and using a throwaway `TEST_DATABASE_URL` if needed. Also run the custom-build `--blender` tests. All must pass.
- [ ] 6.2 Browser pass in the `lamellen-kommode` conversation: ask for the right door to be black with the slats kept.
  - The confirmation names "door 2 black_paint" and shows no front-layout line.
  - On yes, the inspector shows the two doors side by side with the right one black and slatted.
  - The cut list holds `-1` and `-2` door rows and the slat row on door 2.
  - Optionally a **draft** turntable through the render guard; no final.
