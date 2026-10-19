## 1. Service

- [x] 1.1 Add `app/rooms_duplicate.py` with `RoomDuplicateRefused`, `Plan`, `plan` and `create` (design 1–5). Verify with `tests/test_room_duplicate.py`: a shell-only copy has the source's corners, height, wall thickness, openings and notes and no apartment; a name matching another room ignoring case is refused with nothing written; an unknown source and an unknown version are refused.
- [x] 1.2 Copy a chosen layout through `compositions.propose` against the new room, with the change line "duplicated from <room> v<n>", and start its headless build (record `room`). Verify in the same file: the copy's composition v1 has the source version's items and floor and that change line, the start callback is called once, and a layout holding an unapproved piece version is refused naming it, with no room, composition or folder written. Check that the source room's rows and folders are unchanged.

## 2. Route

- [x] 2.1 Add `POST /rooms/{name}/duplicate` in `app/api/rooms.py` (design 6), owner-gated, with a background build starter for `record="room"`. Verify with `tests/test_rooms_api.py`: 201 with the new room and composition, 404 for an unknown room, 409 for a taken name and for a refused layout, and a member account cannot duplicate the owner's room.

## 3. Rooms page

- [x] 3.1 Add `api.duplicateRoom` and `components/DuplicateRoom.tsx`, and wire it into the room dialog in `routes/Rooms.tsx` (design 7). Verify with Vitest (`DuplicateRoom.test.tsx`): the prefilled name, versions newest first with the latest preselected plus "No layout", no layout choice for a room without a composition, the call sent with the chosen version or `null`, and a refusal shown with the form kept open.

## 4. Checks

- [x] 4.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` on a throwaway `TEST_DATABASE_URL` with the RunPod and offload test files skipped, and run `pnpm lint`, `pnpm test` and `pnpm build` in `frontend/`. Report the results.
- [x] 4.2 Browser pass, **no render tier** (nothing renders): duplicate `Wohnen` as "Wohnen (copy)" with the latest layout. Expect the new room in the list, its composition v1 building and then built in the room inspector, and `Wohnen` unchanged. Then duplicate with "No layout" and with a taken name.
