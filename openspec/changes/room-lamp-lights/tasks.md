## 0. Before starting

- [ ] 0.1 Confirm that `composition-ceiling-layer`, `hidden-room-items` and `room-floor-finish` are archived, or at least applied, and rebase this change's edits on their state of `composition_contract.py` and `_composition.py`. Verify that `git status` shows no uncommitted work from those changes in the files this change touches.

## 1. Lighting helpers and config

- [x] 1.1 Add `backend/config/lighting.yaml` with `watts_per_lumen: 0.05`, `rig_factor_with_lamps: 0.5` and `max_lights: 16`. Add `backend/app/blender/lighting.py` with a strict loader (unknown or missing keys refused by name), `lumens_to_watts` and `kelvin_to_rgb` (Tanner Helland, normalised, linear), and load it at startup beside the render tiers in `app/main.py`. Verify with a new `backend/tests/test_lighting.py`: 2700 K is redder than 6500 K, 800 lm gives 40 W, a malformed file is refused naming the key, and startup fails on a malformed file. These tests are written now and run in the final check.

## 2. Contract

- [x] 2.1 In `backend/app/blender/composition_contract.py`, accept an optional `light` on `stand-in` and `model` items through `_parse_light`, with exact keys and ranges. Refuse it on a floor-layer item naming the item and `light`. A piece keeps refusing it as an unknown field. Verify with tests in `test_composition_contract.py` for the scenarios "Pendant with a warm light" (accepted part), "Light on a piece", "Light on a rug", "Unknown light type" and "Brightness out of range".
- [x] 2.2 In `place_items`, record on each lit resolved item `light.at_mm` (footprint centre; z = `base_mm` + 50 for a ceiling item, height − 50 for a standing item, at least half the height), `watts` and `rgb`. Record `rig_factor` on each resolved room, and refuse more than `max_lights` lights naming the limit. Verify with tests for 1450 mm (pendant), 1550 mm (floor lamp), the rig factor 0.5 / 1.0 per room in an apartment, and "Too many lights".

## 3. Generator

- [x] 3.1 Give `build_room_scene._build_lights` an optional `factor` (default 1.0) multiplying its three energies, and pass each room's `rig_factor` from `_composition._build_shells`. Verify with a `--blender` test that a piece room scene's light energies are unchanged and that a lit composition room's are halved.
- [x] 3.2 In `_composition.build_scene`, add `LGT_Lamp_<id>` (`POINT` with a 50 mm radius, or `SPOT` pointing down with a 70° cone and blend 0.3) at `at_mm`, with the resolved colour and watts. Set `visible_shadow = False` on the item's meshes, and add `light` and the room's rig factor to the report. Verify with a `--blender` test in `backend/tests/test_composition_blender.py`: a 2500 mm room with a lit ceiling-layer stand-in and a lit standing stand-in has two lamp lights at the stated heights, with the stated watts and no shadow casting on those meshes, and a document without lights builds an identical report apart from the rig factor 1.0.

## 4. Designer and prompts

- [x] 4.1 Describe `light` (type, lumens, kelvin, with typical values: 400–800 lm per bulb, 2700 K warm, 4000 K neutral) in `ComposeRoomArgs.items` (`backend/plugins/compose_room/tool.py`) and `backend/app/agent/instructions/designer.md`. Show "(light N lm, K K)" in `composition_note` (`backend/app/agent/prompts.py`). Add the `LGT_Lamp_<item id>` naming to `backend/app/agent/instructions/lighting.md`. Verify with a tool-schema assertion in `test_compose_room.py`, a preview test of a lit pendant for confirmation, and a note test in `test_house_file.py`.

## 5. Checks

- [x] 5.1 Run `uv run ruff check .` in `backend/`. Pytest (and the `--blender` suite) is deferred to the batch check after the last change of the 2026-10-18 review batch, skipping the RunPod/offload test files and using a throwaway `TEST_DATABASE_URL`.
- [ ] 5.2 Browser pass, tier **draft**: compose `Wohnen` with the Calisto pendant on the ceiling layer at 800 lm, 2700 K over the dining table, build it, and render a `draft` turntable behind the guard. The table must show a warm pool of light, and the room must still be readable. Record the visual result and, if needed, adjust `watts_per_lumen` and `rig_factor_with_lamps` by hand. A `final` render is optional and only after the owner's typed "yes".
