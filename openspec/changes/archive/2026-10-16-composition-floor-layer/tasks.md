## 1. Contract

- [x] 1.1 In `backend/app/blender/composition_contract.py`, accept an optional `layer` on `stand-in` and `model` items (value `"floor"` only, height ≤ `FLOOR_LAYER_MAX_MM` = 30) and keep it in the normalised item; verify with new tests in `backend/tests/test_composition_contract.py` for an accepted floor rug, an unknown layer value, `layer` on a piece (unknown field) and a 40 mm floor item
- [x] 1.2 In `place_items`, run the overlap check only between items on the same layer, skip `_blocked_opening` for floor-layer items, and leave them out of the returned subjects; verify with tests for a rug under a sofa (accepted), two overlapping rugs (refused naming both), a rug in front of a door (accepted), a rug leaving the room (refused), and the existing overlap and door tests still passing
- [x] 1.3 Verify a floor-layer item gets no placement-rule warning through `compositions.rule_outcome` with a test beside the existing rule tests in `backend/tests/test_composition_contract.py` (rug in front of a door with `door_swing_clear` configured), and that `compose_room` previews a rug under the sofa for confirmation in `backend/tests/test_compose_room.py`

## 2. Designer

- [x] 2.1 Describe `layer: "floor"` for rugs and mats in the `ComposeRoomArgs.items` description (`backend/plugins/compose_room/tool.py`) and in `backend/app/agent/instructions/designer.md`; verify by reading the tool schema in a `test_compose_room.py` assertion
- [x] 2.2 Mark floor-layer items "(floor layer)" in `composition_note` (`backend/app/agent/prompts.py`); carry `layer` through `house_file.placed_items`; verify with a test in `backend/tests/test_house_file.py` beside the existing composition-note tests

## 3. Check

- [x] 3.1 Run `uv run pytest -m "not slow"` (RunPod/offload tests excluded, as this change does not touch them) and `uv run ruff check .` in `backend/`; both pass
- [x] 3.2 Build the Wohnen composition with a floor-layer stand-in rug under `grey-sofa` through the app and render a `draft` turntable behind the guard; the rug appears flat under the sofa
