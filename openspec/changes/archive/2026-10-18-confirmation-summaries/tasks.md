## 1. Backend: titles and table plumbing

- [x] 1.1 Add `CONFIRMATION_TITLES` and `confirmation_title()` to `backend/app/agent/chat.py`, with the 17 subjects from the proposal and "Confirmation" for an unknown one. Write a test that collects every `Confirmation(subject="…")` literal under `backend/plugins/` and asserts each has a title (not run yet, see 4.2).
- [x] 1.2 Add `table: dict | None = None` to `Confirmation` (`backend/app/agent/tools/base.py`). Carry it into the answered record in `backend/app/agent/foreman.py` (around line 1340) and through `_pending_of` / `Pending` in `chat.py`. Write a history test for "Room change keeps its calculations" and "Confirmation answered before titles existed".
- [x] 1.3 Extend `MessageOut` and `PendingOut` in `backend/app/api/chat.py` with `title`, `summary`, `answer`, `reason` and `table`, left out when absent. Update the expectation in `backend/tests/test_chat_api.py` (line 583) by the new keys only. Verify with `uv run ruff check .`.

## 2. Backend: the composition table

- [x] 2.1 In `backend/app/compositions.py`, build `Proposal.table` in the summary loop: Item, Kind, Size (mm), Placement, Centre (mm), Rotation, plus "Hangs at (mm)" when any item is ceiling-layer (only if `composition-ceiling-layer` has landed). Pass it into the confirmation in `backend/plugins/compose_room/tool.py`. Write `test_compose_room.py` tests for "Two items placed" and "Room only", and assert the summary text the tool returns is unchanged.

## 3. Frontend

- [x] 3.1 Add the new fields to the message and pending types in `frontend/src/lib/api.ts`. Change `ConfirmationCard` to head "Confirm: {title}" and render `table` with the shadcn `Table` in an `overflow-x-auto` wrapper. Verify with a `Conversation.test.tsx` case for "Plain heading for a room change".
- [x] 3.2 Replace the "Answered:" paragraph with a collapsed `AnsweredConfirmation` row: title · Yes/No, the reason when given, and a dropdown that shows the summary and table. Update `Conversation.test.tsx` (line 625) and add cases for "Room change collapsed", "Calculations opened", "Declined revision with a reason" and "Collapsed after a reload". Verify with `pnpm test` and `pnpm lint` in `frontend/`.

## 4. Checks

- [x] 4.1 Browser pass, with **no render tier** (nothing is rendered):
  - in a conversation on `Wohnen`, propose a room change and see "Confirm: Composing room" with the item table;
  - answer Yes and see "Composing room · Yes" collapsed; open and close the dropdown; reload and see it collapsed;
  - an older conversation with an answered revision shows "Revising piece · …".
- [x] 4.2 Run `uv run ruff check .` now. pytest is deferred to the batch check after the last change of the 2026-10-18 review batch (skip RunPod/offload tests, throwaway TEST_DATABASE_URL); the tests written above must pass there.
