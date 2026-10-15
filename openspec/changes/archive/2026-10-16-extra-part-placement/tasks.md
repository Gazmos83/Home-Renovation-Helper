## 1. Schema and derivation

- [x] 1.1 Add `ExtraTiltIn` (`towards` x/y/z, `angle_deg` −89…89, not 0) and `ExtraPlacementIn` (`x`, `y`, `z` as `Position`; `length_along`, `width_along` x/y/z, refused when equal; optional `roll_deg` −89…89, not 0; optional `tilt`, refused when `towards` equals `length_along`) in `backend/app/blender/schemas.py`
- [x] 1.2 Add `ExtraEndCutsIn` (`across` width/thickness; `start_deg`, `end_deg` −89…89), and optional `ExtraPartIn.placements` and `end_cuts`
- [x] 1.3 Add `extra_piece_corners` in `backend/app/blender/custom_build/derive.py`: local prism with end cuts, roll, tilt, axis mapping, translation; returns the 8 corners
- [x] 1.4 Validation in `_validate_relationships`: `placements` count equals `qty`; end cuts leave every edge longer than zero; with an envelope, every corner of every placed piece lies inside it; refuse naming the field or part
- [x] 1.5 `overall()` includes the corners of placed pieces; the cut-list row of a part with end cuts gets "ends cut A° / B° across width|thickness" in its notes, with qty and sizes unchanged
- [x] 1.6 Tests in `tests/test_custom_build_spec.py` and the derive tests:
  - helper corners for square-on, rolled, tilted, rolled-and-tilted, parallelogram and trapezoid pieces;
  - count mismatch, equal axes, tilt towards the length axis, a zero angle, cuts that consume the piece, and a turned piece outside the envelope;
  - overall grows without an envelope, unplaced pieces are ignored, and cut-list sizes, hardware and drilling are identical with and without placements

## 2. Generator

- [x] 2.1 `_extra_boxes` draws placed pieces from `extra_piece_corners` as vertex meshes; unplaced parts keep the laid-flat position, drawn with their end cuts. `_frame` includes placed pieces
- [x] 2.2 `--blender` tests in `tests/test_custom_build_generator.py`, each a build with a Workbench screenshot only and no render tier:
  - a placed `top-frame` and an upright `post` have the expected world bounds;
  - a 30° tilted, end-cut `brace` has its far end 866 mm right of and 500 mm above its corner, with plumb ends;
  - an unplaced part still lies beside the build

## 3. Designer

- [x] 3.1 `ExtraPartChange` (`placements`, `end_cuts`, at least one) and `PackageChanges.extra_parts` in `schemas.py`, counted in `_at_least_one`
- [x] 3.2 `backend/app/agent/revise.py`: apply placement and end-cut changes by id, refuse unknown ids and count mismatches, drop equal values, and write change lines ("beside the build" ↔ positions with orientation, roll and tilt; "square" ↔ end cuts); a protruding-shelf fit moves placed pieces with the build
- [x] 3.3 `backend/app/agent/prompts.py`: the Designer summary gives each extra part's name, qty, size, slot, end cuts, and its placements (with roll and tilt) or "beside the build"
- [x] 3.4 `backend/app/agent/instructions/designer.md`: describe `placements`, `roll_deg`, `tilt` and `end_cuts`, with one worked diagonal-brace example, and how to change an existing part through `extra_parts`
- [x] 3.5 Tests in `tests/test_revise.py` and the prompt summary tests: placed, count mismatch, unknown part, a tilted and cut brace, angles in the summary

## 4. Import template

- [x] 4.1 Update the guide in `backend/fixtures/packages/templates/import-template.json`: describe `placements`, `roll_deg`, `tilt` and `end_cuts`, add the brace example, and replace "only modules are drawn assembled"
- [x] 4.2 Extend `tests/test_design_import.py` for the guide scenario; the template is still valid as shipped

## 5. Verify

- [x] 5.1 `uv run ruff check .`, `uv run pytest -m "not slow"`, and the `--blender` suite for the generator tests
- [x] 5.2 Build one version of an existing piece with its extra parts placed, including one tilted, end-cut piece (headless build, Workbench screenshot only, no render tier). Check it in the inspector with the `extras` layer on and off
