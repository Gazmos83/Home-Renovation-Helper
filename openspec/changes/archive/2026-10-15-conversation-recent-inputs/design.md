## Context

See proposal.md for the motivation. What exists:

- **Fitting.** `app/agent/budget.py`: `fit(budget, system, history, …, summarize, trigger_percent, keep_turns, covered_through)` splits the history into `earlier` and `current`.
  - If nothing is covered and `earlier` fits under `trigger_percent` of the usable budget, everything is sent.
  - Otherwise `earlier[:covered]` is forced into the summary, `kept_turns_start` protects the last `keep_turns` owner-started turns, and the rest is trimmed oldest first.
  - The dropped part goes once to `summarize`, whose note is sent in its place, or `HISTORY_OMITTED_NOTE` when no note can be made.
- **Callers.** `prompt_for` in `app/agent/foreman.py` builds the summarizer and `covered_through` only for agent slots (`slot != "foreman"`) on non-engineering turns, and passes `trigger_percent` and `keep_turns` from `read_memory_settings`. The routing call gets no summarizer.
- **Settings.** `MemorySettings` in `app/agent/memory_settings.py`: strict Pydantic, `trigger_percent` 50–100 (default 100; currently stored 70), `keep_turns` 0–20, and others. They are stored as one JSON operator setting, shown on the Agent Memory tab (`frontend/src/routes/admin/Memory.tsx`, a field list) and tested in `tests/test_memory_settings.py` and `Memory.test.tsx`.
- **Measured** on the murphy bed conversation (2026-10-15), as an ordinary turn: all earlier history ≈ 14,000 tokens; last 8 owner inputs ≈ 4,200; last 5 ≈ 70.

## Goals / Non-Goals

**Goals:**
- A bounded, predictable history per call: the recent inputs in full plus one note.
- Reuse the existing summary machinery. No new note type and no new storage.

**Non-Goals:**
- Changing what the note keeps, or making a separate note per agent.
- Capping the current turn's own tool exchanges. A long tool loop within one turn is the current turn and stays mandatory.
- Engineering turns, which already send only their own exchange.

## Decisions

1. **One more cut in `fit`, applied before the trigger test.** `fit(..., recent_inputs: int = 0)`:
   - With `recent_inputs > 0`, `cut = kept_turns_start(earlier, recent_inputs)`, the index of the Nth most recent owner message in `earlier`.
   - `covered = max(_covered(earlier, covered_through), cut)`, so the existing path forces `earlier[:covered]` into the summary.
   - The early return ("everything fits") applies only when `covered == 0`, which already holds today.

   With fewer than N owner inputs, `cut` is 0 and nothing changes. With 0, the old behaviour is kept exactly, so the "setting off" scenario is a parity test. *Alternative:* trimming `history` before calling `fit`. Rejected because the summarizer must see the dropped exchanges to cover them, and `fit` already owns that hand-over.

2. **Turn boundary = owner message.** "Input" means a `HumanMessage`, as in `kept_turns_start`, so a tool call and its result are never split, because both sit inside the turn of the owner message before them. Confirmation answers stored as tool results stay with their turn.

3. **Routing call.** `prompt_for` passes `recent_inputs` for the Foreman too.
   - The Foreman has no summarizer, so `fit` sends the stored note when one covers the cut part. That needs `covered_through` and the stored note text for the Foreman, read-only, through `summaries.covered_through` and the stored summary.
   - Otherwise it sends `HISTORY_OMITTED_NOTE`. It never calls `summarize`.

   *Alternative:* leave routing unbounded. Rejected: routing runs on every turn and was the other half of the 14,000-token cost.

4. **Default 5, stored values kept.** `MemorySettings.recent_inputs: int = Field(default=5, ge=0, le=20)`. Stored settings without the key get the default through the existing merge over `DEFAULTS`. This is the owner's choice (2026-10-15); 0 restores the old behaviour.

5. **Panel field.** Add `{ field: "recent_inputs", label: "Recent inputs sent in full", kind: "number" }` to the Memory page's field list, after "Recent turns always kept in full" (the existing tests address the Save buttons by position), with the API type and the reset button as for the other fields.

6. **Stop the engineering loop by marking the question.** Seen in the murphy bed thread (`a1b8f71f-…`, 2026-10-15): after the stability question, three ordinary messages became engineering turns through the routing model's `engineering_question` flag. The keyword matcher returned false for all of them, because the pattern has "structural" but not "structurally". The checkpoint showed the replies and the tool result marked `engineering`, but never the owner's question.
   - In `request_history`, a turn counts as an engineering exchange when any of its messages carries the marker, the owner's question included. Earlier engineering turns are then left out of later ordinary and routing requests whole, as the existing `marked_turn` path intends. Nothing is written onto the stored owner message, so new and stored conversations behave the same and no data changes. (Applied this way instead of marking the `HumanMessage` in the nodes: in-place marking of a message already in the state is not reliably checkpointed, and the inference covers both cases.)
   - The current turn's own engineering decision is unchanged: keyword match or model flag on the current message.

   *Alternative:* clear `engineering_turn` per turn only. Rejected, because the flag is already recomputed per turn. The stale question in the routing history is what re-triggers it.

## Risks / Trade-offs

- **A detail older than 5 inputs** → it survives only through the note. Mitigation: the owner can raise the setting, or correct the note in the chat. The proposal records the murphy bed case, where the dividers sat about 6–8 inputs back.
- **More summary calls** → once a thread passes 5 inputs, each new turn moves the cut by one input, so the note is refreshed on most turns. That is one extra Foreman-model call with a note of at most 400 tokens. Its input is the newly dropped exchanges plus the old note, which is far smaller than resending the history. Task 5.1 measures it on the murphy bed thread.
- **Parity at 0** → guarded by a test that compares requests with the setting at 0 against today's.
- **Dropping the engineering question** → a later turn no longer sees an earlier engineering question or its status line. That is the intent, since engineering answers are never reused as evidence. A follow-up that is itself an engineering question is still caught by its own wording or the model flag.

## Migration Plan

No data migration. On deploy, existing conversations use 5 at their next call; set 0 on the Agent Memory tab to return to the old behaviour.
