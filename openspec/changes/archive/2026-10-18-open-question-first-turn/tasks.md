## 1. Foreman

- [x] 1.1 In `backend/app/agent/foreman.py`, add `Decision.open_question` and the routing rule after the help rule (no image or design file, no confirmed or declined room, not engineering, not the Researcher) that sends the turn to the Designer with `open_question_turn: True`; reset the flag on every other route. Write foreman tests for "Brainstorming in a new conversation", "The wish after the question gets the room offer", "A request phrased as a question is not brainstorming", "A file is never an open question" and "Help and engineering keep their place" (run deferred, see 3.1).
- [x] 1.2 In `bound_for` and the agent node, limit the Designer to `search_guidelines` on an open-question turn, add `OPEN_QUESTION_NOTE`, and leave out the templates note. Write a test that the Designer's bound tools on such a turn are only `search_guidelines`.

## 2. Instructions

- [x] 2.1 In `backend/app/agent/instructions/foreman.md`, describe when to set `open_question`, with "I'd like to build a kitchen counter, how tall should it be?" (true) and "Can you design a shoe bench for me?" (false). Extend `tests/test_instructions.py` to check the flag is described.

## 3. Checks

- [x] 3.1 Run `uv run ruff check .` in `backend/`. pytest deferred to the batch check after the last change of the 2026-10-18 review batch (skip RunPod/offload tests, throwaway TEST_DATABASE_URL).
- [x] 3.2 Browser pass, with **no render tier**: a new conversation with "I'd like to build a kitchen counter, how tall should it be?" gets a height answer and no room question; "OK, design me one 900 mm high" then gets "Would you like to view this piece in a room?"; the Pieces page shows no new piece after the first turn.
