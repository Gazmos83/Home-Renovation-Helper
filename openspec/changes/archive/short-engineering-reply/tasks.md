## 1. Short status

- [x] 1.1 Add `SHORT_STATUS` in `app/engineering/chat.py` and make `render_answer` start with it, dropping the not-implemented, preliminary-advice, lookup-off, no-evidence, missing-inputs, legal and rejection lines; the rejected path returns only `SHORT_STATUS`. Keep `INSUFFICIENT` for `request_history`. Verify with unit tests: the sentence is at most 20 words; a no-evidence answer and a rejected answer are exactly the sentence; a valid answer with evidence still shows citation and property value; a rejected claim ("safe for 100 kg") never appears.
- [x] 1.2 Update the existing assertions in `test_engineering_chat.py`, `test_kitchen_engineering.py` and `test_engineering_admin.py` that pin the old block text (missing-input needles in the rendered reply move to `missing_inputs()` assertions only).

## 2. Placement is not engineering by the model flag

- [x] 2.1 Add `placement_request(text)` beside `height_question`. Verify with unit tests: the reported message and a German placement ("Stell v18 30 cm von Wand 2") match; "Put the wall cabinet on wall 2, is it safe?", "Can this shelf hold 30 kg?" and "Make it wider" do not.
- [x] 2.2 In `foreman.py`, ignore `decision.engineering_question` when `placement_request` holds. Verify with a graph test: the reported message with a model flag of true is not an engineering turn and its reply carries no not-verified status; a safety question still reaches the engineering path.

## 3. Checks

- [x] 3.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` (one process) and record the results here. Result 2026-10-13, alone on a private database (another session was running pytest on the shared one): ruff clean; pytest -m "not slow" 2521 passed, 42 skipped, 1 failed. The failure (`test_seed_links_registers_kitchen_sources_without_chunks`) is the kitchen seed test already recorded as failing in the full run by simple-height-question-reply; it passes alone and does not touch the rendered reply. `app/engineering/evaluate.py` also changed: its false-verified check now looks for the new sentence.
- [x] 3.2 Owner check: ask a load question and see one short sentence; send the v18 placement message and see the piece placed or a placement question, with no engineering status.
