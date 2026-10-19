## 1. House file

- [x] 1.1 Add `room_declined` to `Thread` in `backend/app/db/models.py`, with an Alembic migration (server default false). Add `house_file.decline_room` and expose the flag where the context node reads the thread. Verify with `uv run alembic upgrade head` on a throwaway database and a house-file test that sets and reads the flag.

## 2. Foreman

- [x] 2.1 In `backend/app/agent/foreman.py`, add `ROOM_OFFER`, the answer reading (`room_answer`: room / yes / no, recording the no) and `room_declined` in the state. Verify with foreman tests for:
  - "New wish";
  - "Owner wants the piece in a room";
  - "Owner names the room straight away";
  - "Owner declines a room";
  - "Not asked again".
- [x] 2.2 Update the router's fixed-reply order, the declined hand-off of the newest pending design to the Designer, and the room-dependent rules (`build_room_ok`, bound piece without a room). Verify with foreman tests for:
  - "Design attached in a new thread";
  - "Design attached, room declined";
  - "Design attached before the room, imported once it is confirmed";
  - "Unassigned piece in a conversation that declined a room";
  - "Designer follows a brief in a conversation that declined a room";
  - "Design file is not a help question";
  - the help-question scenario.
- [x] 2.3 Update every existing test that expects "Which room is this for?" as the first question, so it expects the room offer. Keep the expectation where the owner has already said yes. Verify with `uv run pytest tests/test_foreman*.py tests/test_house_file*.py`.

## 3. Instructions and pieces

- [x] 3.1 Update `backend/app/agent/instructions/foreman.md` and `intake.md` where they quote the room question or say the Designer waits for a room. Verify with `tests/test_instructions.py`.
- [x] 3.2 Verify, with create-piece and import tests, "Imported piece without a room": a piece confirmed in a declined conversation is recorded with no room, and the Pieces API lists it with no room.

## 4. Checks

- [x] 4.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` in `backend/`, skipping the RunPod/offload test files and using a throwaway `TEST_DATABASE_URL` if another session holds the test database. All must pass.
- [ ] 4.2 Browser pass, with **no render tier**:
  - a new conversation with "I want a shoe bench" gets "Would you like to view this piece in a room?"; "no" leads straight to Intake, and no room question follows later;
  - in another conversation, "yes" gets "Which room is this for?";
  - attaching `lamellen-kommode.json` and answering "no" shows the import preview in the same turn.
