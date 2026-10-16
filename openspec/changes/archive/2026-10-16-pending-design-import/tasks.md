## 1. Pending design file

- [x] 1.1 Add `pending_design` and `handoff_design` to `ChatState` in `backend/app/agent/foreman.py`.
- [x] 1.2 In `load_house`, set `pending_design` to the newest design upload named in an owner message's `upload_ids` while the thread has no room, no apartment and no piece. Otherwise set it to `None`. Reset `handoff_design` to `None` every turn.
- [x] 1.3 Unit tests: none while a room is confirmed; none with a bound piece; the newest of two design files; images and notes ignored.

## 2. Hand-off after Intake

- [x] 2.1 Replace the `intake → END` edge with an `after_intake` node. It goes to `designer` only when `pending_design` is set, the thread now has a room or an apartment, and the thread has no piece. On a hand-off it sets `specialist="designer"`, `round_count=0`, `handoff_design`, `room_confirmed` and the refreshed `facts`.
- [x] 2.2 In the Designer's `agent`, append the code-composed note naming the neutralised file name and upload id when `handoff_design` is set.
- [x] 2.3 Graph tests with a fake model (no render):
  - a `confirm_room` yes hands off, and the Designer's `import_design` preview interrupts in the same turn;
  - a `confirm_room` no ends with Intake;
  - a thread with a piece ends with Intake;
  - a "no" to the import preview, followed by a plain message, shows no preview again;
  - `record_brief` naming a stored room hands off.
- [x] 2.5 Draw `after_intake` in the dev panel's workflow map (`/admin/workflow`) as Intake's hand-off to the Designer, not as an agent, which has no routed model and would give a 500. Covered in `tests/test_dev_panel_insights_api.py`.
- [x] 2.4 Check that the existing routing tests for "Design attached in a new thread" and "Design attached after the room is confirmed" still pass unchanged. (The second passes on the committed import template; the working tree's template has two guide notes over 500 characters from other uncommitted work, which refuses it.)

## 3. Intake instruction

- [x] 3.1 Add the line on attached design files to `backend/app/agent/instructions/intake.md`, and update `tests/test_instructions.py` if it pins the text.

## 4. Verify

- [x] 4.1 `uv run ruff check .` and `uv run pytest -m "not slow"` on an isolated test database, skipping the offload and pod test files.
- [x] 4.2 Browser pass: in a new conversation, attach `kommode-harmony.json` with "I'd like to view this dresser", answer "Wohnen" and say yes to the room. Check that the import preview appears in the same turn and that yes lists the piece under Pieces. The import's queued build is a headless blockout and screenshot, not a turntable, so no render tier is involved.
