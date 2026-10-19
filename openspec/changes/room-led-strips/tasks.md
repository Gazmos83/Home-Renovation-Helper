## 0. Before starting

- [ ] 0.1 Confirm that `room-lamp-lights` is applied (`app/blender/lighting.py`, `config/lighting.yaml`, light cap and `rig_factor` present), and rebase on its state of `composition_contract.py` and `_composition.py`. Verify with `git log` / `git status` that no other change in this batch has uncommitted edits in those files.

## 1. Contract

- [x] 1.1 In `backend/app/blender/composition_contract.py`, add `led-strip` to `ITEM_TYPES` and `_ITEM_FIELDS` (`name`, `length_mm`, `lumens_per_m`, `kelvin`, `mount_height_mm`, optional `facing`). Allow the wall placement only, and refuse `layer`, `light`, `colour` and size fields as unknown. Verify with tests in `test_composition_contract.py` for "Free-standing strip", "Size field on a strip" and the range refusals.
- [x] 1.2 In `place_items`, resolve the derived size and `base_mm`, check the wall end and the ceiling, check openings by height on the strip's wall, refuse strip-to-strip overlap on the same wall, skip footprint overlap with other types, leave strips out of the rule subjects, record `watts`, `rgb` and `facing`, and count each strip in the light cap and its room's `rig_factor`. Verify with tests for "Strip under the kitchen wall cabinets", "Strip past the wall end", "Strip across a window", "Strip below a window", "Two strips overlap", a strip pushing the light count over the cap, and the rig factor of a room lit only by a strip.

## 2. Generator

- [x] 2.1 In `backend/app/blender/generators/_composition.py`, add `_place_led_strip`: an emissive bar mesh (length × 15 × 10 mm, kelvin colour, no shadow casting) and an `AREA` `RECTANGLE` light `LGT_Strip_<id>` facing down, up or out, with the resolved watts. Add the report entry and include the bar in the "items" surface. Verify with a `--blender` test in `backend/tests/test_composition_blender.py`: a strip on wall 2 at 1450 mm, facing down, yields a bar of the stated length at that height and a 60 W area light pointing −Z. A facing `up` strip points +Z, and the surface map assigns the bar to "items".

## 3. Designer, prompts and size consumers

- [x] 3.1 Describe `led-strip` in `ComposeRoomArgs.items` (`backend/plugins/compose_room/tool.py`) and `backend/app/agent/instructions/designer.md`, including the hint to re-place strips when a piece on that wall moves. Show the strip in `composition_note` / `_item_place` (`backend/app/agent/prompts.py`), and name `LGT_Strip_<item id>` in `backend/app/agent/instructions/lighting.md`. Verify with a tool-schema assertion and a confirmation-preview test in `test_compose_room.py`, and a note test in `test_house_file.py`.
- [x] 3.2 Check that `app/compositions.py` (proposal summary, `rule_outcome`), `house_file.placed_items`, the dimensions route and the frontend Rooms list handle a strip, using its derived size. Fix any path that reads stated sizes directly. Verify with a test in `test_compose_room.py` that summarises a composition holding a strip, and with `pnpm test` and `pnpm lint` in `frontend/` if any frontend file changes.

## 4. Checks

- [x] 4.1 Run `uv run ruff check .` in `backend/`. Pytest (and the `--blender` suite) is deferred to the batch check after the last change of the 2026-10-18 review batch, skipping the RunPod/offload test files and using a throwaway `TEST_DATABASE_URL`.
- [ ] 4.2 Browser pass, tier **draft**: compose a room with one strip facing down under the line of a kitchen piece and one facing up on top of a tall cabinet, build it, and render a `draft` still behind the guard. Both strips must glow and light the wall and worktop below or the ceiling above. A `final` render is optional and only after the owner's typed "yes".
