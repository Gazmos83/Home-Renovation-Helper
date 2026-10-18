## 1. Contract

- [x] 1.1 In `backend/app/blender/composition_contract.py`, accept `layer: "ceiling"` (constant `CEILING_LAYER`) on `stand-in` and `model` items beside `"floor"`, and keep it in the normalised item. Verify with new tests in `backend/tests/test_composition_contract.py` for an accepted ceiling-layer pendant, `layer: "ceiling"` on a piece (refused as an unknown field), and the existing unknown-layer test still passing.
- [x] 1.2 In `place_items`, give every item a height range: a ceiling item runs from room height minus item height up to the room height, every other item from 0 up to its height. When either item is on the ceiling layer, refuse an overlap only when the footprints overlap and the height ranges overlap; keep the same-layer rule for floor and standing items. Verify with tests for a pendant over a table (accepted), a pendant into a tall cabinet (refused naming both), two overlapping pendants (refused), a rug under a sofa (still accepted), and the existing overlap tests passing.
- [x] 1.3 Run `_blocked_opening` for a ceiling item only when its lowest point is below the opening's top (`sill_mm + height_mm`). Verify with tests for a 300 mm pendant in front of a 2000 mm door in a 2500 mm room (accepted) and a 1100 mm pendant there (refused naming the door and its wall).
- [x] 1.4 Leave ceiling items out of the returned rule subjects, and record `base_mm` on their resolved item. Verify with a test that a ceiling item gets no `door_swing_clear` warning through `compositions.rule_outcome`, and a test that the resolved pendant in a 2500 mm room has `base_mm` 1400 while a standing item has no `base_mm`. Also test that an item taller than its room is still refused, and that a ceiling item leaving the room is refused.

## 2. Generator

- [x] 2.1 In `backend/app/blender/generators/_composition.py`, lift models and pieces in `_pose` and stand-ins in `_place_stand_in` to `base_mm` (default 0), and update the module docstring. Verify with a `--blender` test in `backend/tests/test_composition_blender.py`. The test builds a room with a 2500 mm ceiling holding a ceiling-layer model stated at 500 × 500 × 1100 mm and a ceiling-layer stand-in, and asserts each item's report `lowest_mm` equals its `base_mm`, with its top at 2500 mm. The existing `lowest_mm == 0` assertion becomes `lowest_mm == base_mm or 0`.

## 3. Designer

- [x] 3.1 Describe `layer: "ceiling"` for pendant lamps and other hung items, with the stated height measured from the ceiling down and including the cable, in the `ComposeRoomArgs.items` description (`backend/plugins/compose_room/tool.py`) and in `backend/app/agent/instructions/designer.md`. Verify with an assertion on the tool schema in `backend/tests/test_compose_room.py`, plus a test that `compose_room` previews a pendant over a table for confirmation.
- [x] 3.2 Mark ceiling-layer items "(ceiling layer)" in `composition_note` (`backend/app/agent/prompts.py`). Verify with a test in `backend/tests/test_house_file.py` beside the existing floor-layer note test.

## 4. Check

- [x] 4.1 Run `uv run pytest -m "not slow"` (excluding the RunPod and offload tests, which this change does not touch), `uv run pytest --blender backend/tests/test_composition_blender.py` and `uv run ruff check .` in `backend/`. All must pass.
- [x] 4.2 The owner uploads `pendelleuchte-calisto.glb` to the model library as 500 × 500 × 1100 mm. Then build a room composition with it over the dining table as a ceiling-layer model through the app, and render a `draft` turntable behind the guard. The lamp must hang from the ceiling with its shade above the table.
  Done 2026-10-18 as Wohnen v15: the 1100 mm Calisto would hang into the dining table's flowers (1492 mm), so the owner chose a 1000 mm build (`Pendelleuchte Calisto natur (1,0 m)`). v15's report gives `lowest_mm` 1500, and in `model.glb` the canopy is at 2475–2500 mm. The owner marked the task complete without the `draft` turntable.
