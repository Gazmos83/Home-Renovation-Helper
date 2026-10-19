Before starting: `composition-ceiling-layer` is committed and archived. This change is ~90 min of work. pytest is not run per task (decided 2026-10-18); tests are written alongside the code and run in the batch check (5.1).

## 1. Contract

- [x] 1.1 In `backend/app/blender/composition_contract.py`, accept an optional boolean `hidden` on every item type in `_parse_item`, keeping it only when true and refusing any other value by item and field. Write tests in `backend/tests/test_composition_contract.py` for "Hidden sofa accepted", "Hidden piece accepted", "Hidden false is the same as no flag" and "Hidden must be true or false". Verify with `uv run ruff check .`.
- [x] 1.2 In `place_items`, keep the ceiling, wall and outline checks for a hidden item. Skip its opening check, leave it out of `footprints` and the overlap comparison, leave it out of the rule subjects, and record `hidden: true` on its resolved item. Write tests for "Hidden sofa overlaps the armchair", "Hidden item in front of a door" (no `door_swing_clear` warning through `compositions.rule_outcome`) and "Hidden item still inside the room". Verify with `uv run ruff check .`.

## 2. Composition service and Designer

- [x] 2.1 In `backend/app/compositions.py`, make `_changes` emit `hidden: <id>` / `shown: <id>` when only the flag differs, and mark hidden items in the proposal summary. In `backend/app/agent/house_file.py`, `placed_items` copies `hidden`, and in `backend/app/agent/prompts.py`, `composition_note` appends "(hidden)". Write tests in `test_compose_room.py` (summary and change line, "Hidden piece still approved") and `test_house_file.py` (note marker). Verify with `uv run ruff check .`.
- [x] 2.2 Describe `hidden: true` and how to show an item again in the `ComposeRoomArgs.items` description (`backend/plugins/compose_room/tool.py`) and in `backend/app/agent/instructions/designer.md`. Write a tool-schema assertion in `test_compose_room.py`. Verify by reading the rendered description.

## 3. Generator

- [x] 3.1 In `backend/app/blender/generators/_composition.py`, make `build_scene` skip hidden items, listing each with `{id, type, hidden: true}`, and add `name` and `meshes` to every built item's report entry. In `backend/app/blender/runner.py`, `composition_unbuilt_pieces` skips hidden pieces. In `backend/app/blender/verify.py`, check that report item meshes are under `items` and that none is listed twice. Write `--blender` tests in `backend/tests/test_composition_blender.py` for "Hidden sofa left out of the build", "Only hidden items" and "Item meshes listed", plus a plain test for the verify check. Verify with `uv run ruff check .`; the Blender suite runs in 5.1.

## 4. Frontend

- [x] 4.1 Add `items?: {id, type, name?, meshes?, hidden?}[]` to `CompositionReport` in `frontend/src/lib/api.ts`. In `frontend/src/components/inspector/RoomView.tsx`, when every built item lists `meshes`, replace the `items` switch with one switch per item (layer `item:<id>`, placed first in the layer map) plus "All items". Write a Vitest test covering "One item switched off", "All items" and "Older report keeps one items switch". Verify with `pnpm test` and `pnpm lint`.
- [x] 4.2 In `frontend/src/routes/Rooms.tsx`, mark a hidden item with a "hidden" badge in the item list. Write a Vitest test for "Hidden item listed, not switched". Verify with `pnpm test`, `pnpm lint` and `pnpm build`.

## 5. Checks

- [x] 5.1 Batch check: pytest and the `--blender` suite are deferred to the batch check after the last change of the 2026-10-18 review batch. Run them there, skipping the RunPod/offload tests and using a throwaway `TEST_DATABASE_URL`: `uv run pytest -m "not slow"`, `uv run pytest --blender tests/test_composition_blender.py`, and `uv run ruff check .`. All must pass.
- [x] 5.2 Browser pass (render tier **draft**):
  - in a conversation for `Wohnen`, ask the Designer to hide the sofa and confirm. The new version lists the sofa as "hidden" on the Measured Rooms page, and its 3D view has no sofa switch;
  - in the previous version's 3D view, switch the armchair off and on, and use "All items". No version is created;
  - render a `draft` turntable of the new version behind the guard. The sofa is not in any frame.
