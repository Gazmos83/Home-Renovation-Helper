## 1. Progress read

- [x] 1.1 Add `room_progress(session, root, thread_id)` beside `piece_progress` in `backend/app/agent/progress.py`: the conversation's room or apartment from `thread_scope`, its composition from `composition_by_scope`, and the latest version's `model.glb` and `report.json` routes (the same route shape as `GET /compositions`), or `None` with no scope. Verify with `test_progress.py` cases for no scope, no composition, a model, a latest version without a model, and an apartment.
- [x] 1.2 Add `RoomOut` and `room: RoomOut | None` to `ProgressOut` and fill it in `read_progress`. Verify with `test_chat_api.py`: the route returns the thread's own room, not another thread's or the piece's room, and the body has no host path.

## 2. Project panel and split screen

- [x] 2.1 Add the `room` field to the `Progress` type in `frontend/src/lib/api.ts`. Verify with `pnpm build` (type check).
- [x] 2.2 In `ProjectPanel`, add the room section under the piece: the name, "Inspect <name>" when a model is known, the "no 3D view yet" note when there is no composition, the "composing again" note when the latest version has no model, and nothing without a scope. Verify with `Conversation.test.tsx`.
- [x] 2.3 Add the `?room=<slug>` parameter and show `RoomView` in the existing side pane with the room's name and a close control, only when the slug matches the progress room with a model; opening the room clears `?inspect=` and opening a version clears `?room=`. Verify with `Conversation.test.tsx` for open, close, reload from the address, a stale slug, and one pane at a time.

## 3. Checks

- [x] 3.1 Run `uv run ruff check .`, `uv run pytest -m "not slow"` (one process), `pnpm lint`, `pnpm test` and `pnpm build`, and record that all are green.
  Green 2026-10-09: ruff clean; pytest 2091 passed, 36 skipped (6 min; a first run overlapped another test process on the shared database and was discarded); oxlint clean; Vitest 204 passed (24 files); `pnpm build` built.
- [x] 3.2 Run a browser check of the Project panel's room section (inspect, close, reload, one pane at a time, the no-3D note) on an existing composition with `model.glb` in a scratch database. No build or render runs (no tier). Record the result here.
  Browser pass 2026-10-09: headless Chromium through Python Playwright, scratch database `home_renovation_room_ui` (dropped afterwards), a copy of composition `wohnen` v2 (with `model.glb`) and `listening-wall` v14 as v1 in the session scratchpad, backend on 8100 and Vite on 5180; the owner's 8000 and 5173 were untouched. No build or render ran. All 6 checks passed: "Inspect Wohnen" opens the room beside the chat (chat left, room right) with its surface switches, the ceiling off and the canvas drawn, and the composer usable; a reload shows it again; "Inspect version 1" replaces it with the piece inspector and "Inspect Wohnen" replaces that again; closing it removes `?room=`; a conversation in `Hall` (no composition) shows "Hall has no 3D view yet. Ask the Designer to compose the room." and no button.
- [x] 3.3 Owner check in the app: open the conversation's room from the Project panel beside the chat.
  Passed by the owner 2026-10-09, with three additions asked for (sections 4–6).

## 4. Room versions (added 2026-10-09)

- [x] 4.1 Add `composition_version_views` in `backend/app/agent/progress.py` (newest five, newest first, with status, picture, viewer, items and the model, surfaces and dimensions routes when `model.glb` exists); add it to `GET /compositions` as `version_views` and to the progress room as `versions`. Verify with `test_progress.py`, `test_compositions_api.py` and `test_chat_api.py` (seven versions list 7–3; a version without a model has no 3D routes).
- [x] 4.2 On the Rooms page, add a version dropdown per composition (newest five, latest chosen) and make the status, items, picture, viewer link and 3D view follow it. Verify with `Rooms.test.tsx`.
- [x] 4.3 Beside the chat, accept `?room=<slug>/<n>`, add the same dropdown to the room pane, and name a version without a 3D model in words. Verify with `Conversation.test.tsx` (choose, reload, unknown number shows the latest).

## 5. Room dimensions (added 2026-10-09)

- [x] 5.1 Add `room_dimensions(document)` in `backend/app/compositions.py` (room: one wall per polygon edge; apartment: the shell's unique walls with their labels; each room's ceiling height and marker point) and `GET /compositions/{slug}/versions/{n}/dimensions` (404 for an unknown or unreadable version). Verify with tests for `Wohnen` (6200, 5700, 2700, 2241, 6199 mm; 2500 mm), an apartment with a shared wall and a differing room height, and the 404.
- [x] 5.2 Add an optional `overlay` to `InspectorCanvas`, a `RoomDimensions` overlay, and a "dimensions" switch (off at first) in `RoomView` that loads the chosen version's dimensions. Verify with `Rooms.test.tsx` (switch state, the dimensions route is fetched only when switched on, overlay props) and the wall-to-stage coordinate maths in a unit test.

## 6. Panel heading and checks (added 2026-10-09)

- [x] 6.1 Head the Project panel's room section "Selected room" above the room's name. Verify with `Conversation.test.tsx`.
- [x] 6.2 Run `uv run ruff check .`, `uv run pytest -m "not slow"` (one process), `pnpm lint`, `pnpm test` and `pnpm build`, and record that all are green.
  Green 2026-10-09: ruff clean; pytest 2096 passed, 36 skipped (9 min, one process); oxlint clean; Vitest 210 passed (24 files); `pnpm build` built.
- [x] 6.3 Run a browser check: the Rooms page dropdown and dimensions on `wohnen` with at least two versions, and the pane beside the chat with "Selected room", its dropdown, a reload on an older version, and dimensions. Use existing builds only; no build or render runs (no tier). Record the result here.
  Browser pass 2026-10-09: same setup as 3.2 (scratch database dropped afterwards; ports 8100/5180; owner's servers untouched), with `wohnen` v1 (no `model.glb`) and v2 copied. No build or render ran. All 5 checks passed: the Rooms page dropdown lists "Version 2", "Version 1" with 2 chosen, and dimensions label wall 1–5 as 6200, 5700, 2700, 2241 and 6199 mm and "ceiling 2500 mm"; choosing v1 shows its picture and "Composing Wohnen again adds the 3D view."; the Project panel shows "Selected room" above "Wohnen"; the pane beside the chat offers the dropdown on v2 and the same dimension labels; choosing v1 there says it has no 3D view, puts `room=wohnen/1` in the address, and a reload keeps version 1.
- [x] 6.4 Owner check in the app: the "Selected room" heading, the version dropdown and the dimensions.
  Accepted by the owner 2026-10-10.
