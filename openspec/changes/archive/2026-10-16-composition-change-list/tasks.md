## 1. Designer instruction

- [x] 1.1 In `backend/app/agent/instructions/designer.md`, extend the `compose_room` rule: when the room or apartment already has a composition version, first restate the changes as a short list (one line per item added, moved or removed, by its id from the composition note) and ask whether anything else should change; call `compose_room` only once the owner says the list is complete, carrying every change since the latest version in that one call; add a further change and ask again; a decline reason is one more change, restate the whole list, and do not call `compose_room` again in that reply; a first composition needs no restating. Verify by reading the rule next to the `revise_package` one.

## 2. Tests

- [x] 2.1 Add `test_the_designer_restates_a_composition_change_and_asks_before_calling_the_tool` to `backend/tests/test_instructions.py`, asserting the new phrases; verify with `uv run pytest tests/test_instructions.py` in `backend/`.
- [x] 2.2 Run `uv run pytest -m "not slow"` and `uv run ruff check .` in `backend/` and verify both pass.

## 3. Live check

- [x] 3.1 In a conversation bound to `Wohnen`, ask to remove one item and verify that the Designer restates it and asks whether anything else should change, with no confirmation raised. Then add a second change, say that is all, and verify that one summary lists both changes. No render is needed: answer `no` to the summary, or render only a `draft` tier turntable.
