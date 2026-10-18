## 1. Placed sizes in the composition note

- [x] 1.1 In `backend/app/agent/house_file.py`, have `placed_items` merge `resolved.items` by id (`size_mm`, `centre_mm`, `rotation_deg`), leaving items without a resolved entry unchanged. Verify with `tests/test_house_file.py`: "Placed sizes reach the Designer" (house-file side) and "Document without resolved placement".
- [x] 1.2 In `backend/app/agent/prompts.py`, extend `_item_place`/`composition_note` with size, centre and rotation, and explain the coordinates once in `COMPOSITION_PREAMBLE`. Verify with `tests/test_prompts.py` for the listening-wall line and the unchanged line without resolved data.

## 2. Routing

- [x] 2.1 In `backend/app/agent/foreman.py`, let `room_wish` turn a `builder` choice into `designer`, as it does `intake`. Verify with `tests/test_foreman.py`: "Move after a composition was built" and "Render still goes to the Builder".
- [x] 2.2 Add to `foreman.md` that moving, adding, removing or re-placing an item in a composed room is composing it. Verify with `tests/test_instructions.py`.

## 3. compose_room hand-off

- [x] 3.1 In `tools_node`, a lone `compose_room` call by a non-Designer with the plugin enabled sets `handoff_compose`, runs nothing and ends the round (the specialist sub-graph's static `tools → agent` edge is dropped so the node's `Command` decides). Add a routing step after non-Designer specialists that drops the round's AI message and tool result, adds the Designer note and goes to `designer` (at most once per turn). Verify with `tests/test_foreman.py`: "Builder calls compose_room" (no Builder text or refusal in the stored history, Designer reply present) and "compose_room beside other calls" (refusal as today).

## 4. Role note and no relaying

- [x] 4.1 Append the fixed role note to every specialist's prompt in `specialist_graph.agent`. Verify with a foreman test that the Designer's system prompt names the Designer and carries the note.
- [x] 4.2 Update `designer.md` (take sizes and positions from the composition note; a piece's room depth is the note's d) and `builder.md` (a room change: one sentence that the room has not been changed; no change list, no relaying), and remove any "pass it on" wording elsewhere. Verify with `tests/test_instructions.py`.

## 5. Checks

- [x] 5.1 `uv run ruff check .` and `uv run pytest -m "not slow"` (excluding the RunPod/offload files, on a throwaway `TEST_DATABASE_URL` if another session is using the test database). The `/admin/workflow` map treats `after_specialist` as a hand-off step (`app/api/admin_workflow.py`). 2026-10-18: 3031 passed; 4 failures are from other sessions' uncommitted work (pricing approval wording, migration head 0031), not this change.
- [x] 5.2 Browser pass: in `Wohnen`, ask to move the dining table right after a build; the Designer restates the change with the listening wall's 562 mm depth from the note and no question about its width, and after "yes" a new version is created.
