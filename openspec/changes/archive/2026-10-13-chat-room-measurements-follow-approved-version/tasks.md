## 1. Dimensions in the room block

- [x] 1.1 Give `house_note` an optional per-room dimensions argument and print wall lengths, ceiling heights and the version label (approved / not approved), keeping the house-file line when absent
- [x] 1.2 In `foreman.py`, resolve the scope room's approved (else latest) composition version and fill the dimensions from `compositions.room_dimensions`, for room and apartment scopes
- [x] 1.3 Add the "supersedes earlier quotes and the conversation note" sentence to the house preamble

## 2. Read tool

- [x] 2.1 Add the read-only version-dimensions tool, room from thread scope, version as the only model argument, refusing other rooms and unknown versions with a stated reason
- [x] 2.2 Register it (manifest, role, toggle rules as for neighbouring read tools)

## 3. Tests and check

- [x] 3.1 Tests: Wohnen v2 block lists the five walls and 2500 mm; approving v3 changes the next block; no approved version labelled; no composition keeps house-file figures; tool refuses another room
- [x] 3.2 Test that the chat figures equal the dimensions route's for the same version
- [x] 3.3 Run `uv run pytest -m "not slow"` and `uv run ruff check .`; owner re-asks the Wohnen question in chat and compares with the inspector
  - pytest (`not slow`: 2387 passed / 39 skipped / 26 deselected; one unrelated flaky kitchen seed test failed in the suite and passed alone) and `ruff check .` done 2026-10-12
  - Owner check 2026-10-13: wall-length quote OK; placement still used house-file door on wall 2 → extend with §4
  - Owner pass 2026-10-13: Wohnen wall lengths in chat match the inspector

## 4. Placement uses the same plan

- [x] 4.1 Add `placement_room` (approved else latest composition resolved room as house-file-shaped corners/openings/height); fall back to None when absent
- [x] 4.2 `room_fit` uses `placement_room` when present
- [x] 4.3 `compose_room` / `_rooms_in_scope` prefers that plan for room scope
- [x] 4.4 Tests: house-file door ignored when approved plan has none; no composition still uses house-file door; re-run room_fit and chat-room measurement tests; owner retries the listening-wall placement
  - Automated tests done 2026-10-13 (`test_room_fit`, `test_chat_room_measurements`, `test_compose_room`: 32 passed; ruff clean)
  - Owner retry hit NetworkError on fetch (SSE idle drop on multi-minute turns). Fix 2026-10-13: SSE keepalive every 15s; Vite `/chat` timeout/proxyTimeout 0; designer/room_fit note that house-note "wall 2" is tool index 1 (door at 850-1850 is labelled wall 3 / index 2). Restart uvicorn + Vite, then retry placement.
  - Owner pass 2026-10-13: listening-wall placement along wall 2, one meter from wall 3, succeeded after the SSE/proxy fix
