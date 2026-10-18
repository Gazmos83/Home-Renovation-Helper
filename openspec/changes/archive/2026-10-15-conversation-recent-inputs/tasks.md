## 1. Setting

- [x] 1.1 Add `recent_inputs` (0–20, default 5) to `MemorySettings`. Verify with `tests/test_memory_settings.py` cases: the default is 5, 8 is stored, 21 and -1 are refused naming the field, reset restores 5, and stored settings without the key read 5.

## 2. Fitting

- [x] 2.1 Add `recent_inputs` to `fit`/`prepare` (design decision 1). Verify with `tests/test_budget.py` cases from the token-budget delta: only the recent inputs are sent (40 inputs, setting 5: summary + 5 inputs + current), short thread unchanged (3 inputs, no summary call), setting 0 equals today's request for the same history, and no tool call is split from its result.
- [x] 2.2 Pass the setting from `prompt_for` for agent slots, and for the Foreman with the stored note read-only and no summary call (design decision 3). Verify with Foreman tests: an agent call on a 40-input thread sends the note and 5 inputs; the routing call sends the stored note, or the shortened-history note when none is stored, and makes no summary call.

## 3. Developer panel

- [x] 3.1 Add "Recent inputs sent in full" to the Agent Memory tab and the API type (design decision 5). Verify with `Memory.test.tsx` cases (shows default 5, saves 8, shows the out-of-range refusal next to the field, reset), `pnpm lint` and `pnpm build`.

## 4. Engineering loop

- [x] 4.1 Mark the owner's message of an engineering turn, and treat an owner message whose turn carries an engineering marker as marked in `request_history` (design decision 6). Verify with tests from the homeowner-chat delta: the reported loop (a stored question + status reply + "Keep and shorten the dividers." → that turn is not engineering, and the routing request omits the question), a new engineering question is still one, and a stored unmarked conversation recovers with its messages unchanged.
- [x] 4.2 Replay the murphy bed conversation's stored history through the routing request builder. Verify that the stability question and its three status replies are absent and "Keep and shorten the dividers." is present.
  Replay 2026-10-15 of the stored murphy bed history (`chat:a1b8f71f-…`, 103 messages) plus "Keep and shorten the dividers." through `request_history(routing=True)`: the stability question is absent, 0 status replies remain, the new message is last, and the cut-list reply naming `bridge-dividers` is present (59 messages sent). Read-only; the stored thread is unchanged.

## 5. Checks

- [x] 5.1 Measure on a copy of the murphy bed conversation's history: tokens sent by a Designer call and a routing call with the setting at 5 and at 0, and the summary calls made over three further turns, with task 4 in place. Record the figures in design.md. Verify by the recorded numbers.
  Measured 2026-10-15 on the stored murphy bed history (103 messages) plus "Please shorten the dividers", with the loop fix in place, a 50,000-token budget, 70 % trigger, and a note at its 400-token cap as the upper bound. These are counts from `budget.count`, with no model calls. Designer call: ≈ 6,200 history tokens with the setting at 5 (22 messages, note included), against ≈ 13,900 at 0 (89 messages). Routing call: ≈ 4,600 against ≈ 8,800. The last 5 inputs are larger than the ≈ 70 tokens estimated before the fix, because the latest turns now hold the owner's newer, longer exchanges. Summary calls were not run live. By design each further turn moves the cut by one input, so there is one note refresh per turn on the Foreman model, whose input is the newly dropped exchange plus the old note.
- [x] 5.2 Run `uv run ruff check .`, `uv run pytest -m "not slow"`, and `pnpm test`, `pnpm lint` and `pnpm build`. Verify that all pass, and record any failure that belongs to another change.
  Run 2026-10-15: `ruff check .` clean; `pytest -m "not slow"` 2696 passed, 42 skipped, 1 failed: `test_kitchen_engineering.py::test_seed_links_registers_kitchen_sources_without_chunks`, the known test that depends on what other tests leave in the shared database (it passes alone; unrelated). `pnpm test` 426 passed; `pnpm lint` and `pnpm build` clean.
