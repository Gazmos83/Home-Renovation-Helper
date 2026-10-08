## 0. Preconditions

- [x] 0.1 Confirm that `conversation-projects` is implemented: `app/api/rooms.py` serves `GET /rooms`, `PUT /packages/{id}/room` exists, and migration `0014_conversation_rooms` gives `threads.room_id` and `pieces.room_id` `ON DELETE SET NULL`. Verify by reading the migration and `uv run pytest tests/test_conversation_rooms_migration.py`. Stop and ask if any is missing.

## 1. Empty room composition (contract and tool)

- [x] 1.1 In `app/blender/composition_contract.py` `parse_composition`, allow an empty `items` list for a room scope, and refuse it for an apartment with "an apartment composition needs at least one item". The other item checks stay unchanged. Verify that `tests/test_composition_contract.py` covers the "Empty room" and "Empty apartment refused" scenarios, and that `place_items` on an empty room returns `resolved.rooms` holding the room and an empty `resolved.items`.
- [x] 1.2 In `app/compositions.py`, make the summary of an empty room read "Room <name>: the room only, no items". Removed items against the latest version stay listed as today. Update the `items` description in `plugins/compose_room/tool.py` to say a room may be composed with no items. Verify that `tests/test_compose_room.py` covers an empty room confirmed (version 1, build started), the last item removed (summary lists it, version 2 empty), and an empty apartment refused without a pause.
- [x] 1.3 Add one line to `app/agent/instructions/designer.md`: when the owner wants the room with no furniture, call `compose_room` with the room and an empty item list. Verify with `uv run pytest tests/test_instructions.py`.

## 2. Routing

- [x] 2.1 In `app/agent/foreman.py` `load_house`, set `compose_ready` also when the conversation has a confirmed room (not an apartment alone), as in design decision 6. In `tests/test_foreman.py`, `test_a_compose_request_in_a_new_thread_reaches_the_designer_once_a_piece_is_approved` asserts Intake for "compose Wohnen with my furniture" while nothing is approved. Change that assertion to the Designer, with a comment naming this change, because the owner's decision reverses it. Add a test for the "Empty room compose request in a new thread" scenario, and keep one test showing that a thread with no confirmed room still gets "Which room is this for?". Verify with `uv run pytest tests/test_foreman.py`.

## 3. Headless build of an empty room (ladder step 1, step 2 only if needed)

- [x] 3.1 Add an empty-room case to `tests/test_composition_blender.py`. It builds `Hall` with no items through `build_composition.py`, then checks that `model.blend` holds the room's walls, floor and ceiling and no `ITEM_` object, that `report.json` has `items: []`, and that the screenshot exists. It then renders one still at tier `draft` (600 × 600, Eevee) through `render_composition.py`, with the tier arguments the runner passes. Run `uv run pytest -m slow --blender -k composition` with Blender 5.2.1. Verify that it passes, including the existing composition tests.
- [x] 3.2 (Not needed: 3.1 passed with no generator change.) Only if 3.1 fails: make the smallest generator fix in `app/blender/generators/_composition.py` or `build_composition.py` (ladder step 2), with no change to the contract shape, and run `uv run pytest -m slow --blender -k composition` again. Verify that it passes and that `uv run pytest -m slow --blender -k room_scene` still passes. If 3.1 passes, tick this task as not needed and say so.

## 4. Room summaries and deletion (backend)

- [x] 4.1 Add `room_summaries(session, render_root)` to `app/agent/house_file.py`, returning the fields of design decision 1: bounding width and depth, corner count, height, opening count, apartment name, pieces by package id and name, the count of threads whose `room_id` is the room, and the room composition's slug and version numbers. Change `GET /rooms` in `app/api/rooms.py` to return these summaries. Update the `GET /rooms` assertion in `tests/test_packages_api.py` to the new shape (necessary, since the shape changes). Verify that `tests/test_house_file.py` covers the "Rooms listed with their details" scenario.
- [x] 4.2 Add a helper to `app/blender/storage.py` that moves a composition's folder aside to a hidden `.deleted-<slug>-<hex>` sibling and can move it back. Verify that `tests/test_storage.py` covers move aside, move back, and that `list_compositions` ignores the hidden folder.
- [x] 4.3 Add `delete_room(session, render_root, name)` to `app/agent/house_file.py`, following design decision 2: refuse an apartment room and a composition with a build or render `queued` or `running`, move the folder aside, delete the composition and room rows in one transaction, move the folder back on failure, and remove it after the commit. Verify that `tests/test_house_file.py` covers the "Room deleted" scenario (pieces unassigned with their versions, thread room cleared, composition rows and folder gone), "Other compositions kept", "Room in an apartment", "Build running", and a forced commit failure that leaves the folder and rows in place.
- [x] 4.4 Add the owner-gated `DELETE /rooms/{name}` to `app/api/rooms.py`: 204 on success, 404 for an unknown room, 409 with the reason for an apartment room or a running build or render. Verify with a new `tests/test_rooms_api.py` covering 401 without the cookie (for both routes), 404, both 409 cases, and 204 followed by a `GET /rooms` without the room. Add `("DELETE", "/rooms/x")` to the owner-gate route list in `tests/test_packages_api.py`, beside `("GET", "/rooms")`.
- [x] 4.5 Check that a conversation whose confirmed room was deleted gets "Which room is this for?" on its next design turn. Verify with a test in `tests/test_foreman.py` for the "Next turn in that conversation" scenario.

## 5. Studio

- [x] 5.1 In `src/lib/api.ts`, add the `RoomSummary` type, change `rooms()` to return `RoomSummary[]`, and add `deleteRoom(name)`. In `src/routes/Pieces.tsx`, map `room.name` in the room selector. Update the `GET /rooms` mocks in `src/routes/Pieces.test.tsx` to return summaries (necessary, since the shape changes). Verify with `pnpm test Pieces`.
- [x] 5.2 In `src/routes/Rooms.tsx`, add the "Measured rooms" section above the compositions:
  - each room's size, ceiling height, openings, apartment, pieces and whether it has a composition;
  - the inline confirm step for delete, naming the affected pieces, conversations and composition versions;
  - the apartment-room reason in place of the delete action;
  - a refusal shown next to the room;
  - on success, invalidating `rooms`, `compositions` and `pieces`.

  Show "The room only, no furniture" for a composition with no items. Keep "Open the turntable viewer of <composition>". Verify that `src/routes/Rooms.test.tsx` covers the scenarios "Measured room listed", "Delete warns first", "Delete cancelled" (no request sent), "Delete confirmed", "Room in an apartment", "Delete refused" and "Empty composition shown".
- [x] 5.3 Run `pnpm lint` and `pnpm build` in `frontend/`. Verify that both pass.

## 6. Verification

- [x] 6.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` in `backend/` (one pytest process at a time). Verify that both pass.
- [x] 6.2 Do a recorded browser check of the Rooms page:
  - a measured room with a piece is listed;
  - the delete dialog names its effects, and cancel keeps the room;
  - composing that room empty from a conversation gives a built version shown as "The room only, no furniture" with its screenshot;
  - a `draft` still of it is requested from the conversation, its estimate is stated, and it renders through the guard;
  - deleting the room removes it and its composition, and the Pieces page shows its piece with "No room".

  Verify that the recording is saved with the change notes.
- [ ] 6.3 Run `openspec validate rooms-page --strict`. Verify that it passes. Before archiving, confirm that `conversation-projects` is archived first, because the `design-agents` routing delta starts from its text.
