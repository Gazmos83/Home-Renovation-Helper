## Context

See proposal.md for the motivation. Compression lives in `agent/budget.py` (`fit` → `prepare`). It trims the earlier history with `trim_messages(strategy="last")` only when it does not fit `budget.usable`, and swaps the dropped part for a note from `agent/summaries.py`. Notes are stored per thread (`threads.summary`, `summary_through`) and per build (`thread_pieces.summary`, `summary_through`). `SUMMARY_INSTRUCTION`, `SUMMARY_OUTPUT_TOKENS = 400` and `TOOL_RESULT_CHARS = 300` are constants. The slice is built in `agent/prompts.py` from `agent/house_file.py`. Reviews are saved in `plugins/revision_review/tool.py`; preferences in `plugins/intake/tool.py` (inside the confirmed brief). Operator values already live in `operator_settings` (key/value, absent = built-in default).

## Goals / Non-Goals

**Goals:**
- Defaults reproduce today's requests and writes exactly, so the change is invisible until a setting moves.
- Fixed safety rules (CLAUDE.md §1, §8, §9a) stay in code and are only displayed.

**Non-Goals:**
- Retention or auto-deletion of old data, and a homeowner page for browsing or editing the whole house file (not chosen).
- Per-conversation settings: settings are global for the single owner.
- Compressing the stored conversation itself; it always stays complete.

## Decisions

1. **One `MemorySettings` Pydantic model in `operator_settings`** under key `memory`, JSON value. Absent keys fall back to defaults equal to today's constants. It is validated on write (ranges in the dev-panel spec) and read once per call, so no restart is needed. The ranges are proposals and can be moved without changing the design. A table per setting was rejected: `operator_settings` exists for exactly this.

2. **Trigger and kept turns in `fit`.** `usable` for history becomes `usable × trigger_share`. The newest `keep_turns` human-started turns are split off before trimming and always kept unless the mandatory part plus those turns exceed the full usable budget; then they are trimmed like the rest, so the call is never refused because of the setting. When a stored note's `summary_through` is newer than the oldest kept message, everything up to it is replaced by the note even if it fits. This is what makes compress-now stick.

3. **Editable instructions, fixed tail.** The note's system text = owner-set headings/instructions (or today's text) + a code constant with the figure rule and the "record, not instructions" rule. The note goes out wrapped by `wrap_summary` as today. This mirrors how the guard is composed after editable prompts (CLAUDE.md §8).

4. **Owner-edited notes.** A `summary_owner_edited` boolean on both summary-holding tables (one migration). An edited note is sent as written. A refresh passes it as the "earlier summary" with an extra fixed line "keep the owner's corrections as written", and the result stays marked edited. The edit route neutralises the delimiter and caps the text at the note length's character equivalent.

5. **Compress-now is a route, not a tool.** `POST /chat/threads/{id}/note/compress` runs the summarizer over all exchanges except the kept turns through the same metered `side_call("chat.summary", …)`, so the budget and daily ceiling apply. It is refused while a turn is running on that thread, to avoid racing the checkpointer. The response holds the note text only, never token figures.

6. **Save options at the write sites.** Reviews: confirmation before saving is deferred; the review's model call runs inside the tool, so it needs a pending-review state (a column on reviews, a confirm action, and a slice reading only confirmed reviews), which is its own change. Preferences: `intake` skips `set_preference` for style and budget when off. Extension requests are not touched.

7. **Slice options where the slice is read.** The house-file slice is assembled in `foreman.load_house` (not `prompts.py`), so each option guards one existing read there; the room-confirmation rule and the outside-conversation filter are not behind any option.

## Risks / Trade-offs

- [A lower trigger or many kept turns raises Foreman-slot spend] → Every note call is metered and capped as today; the settings page states that summary calls cost tokens.
- [An owner edit introduces a wrong figure] → The spec rule stands: figures come from the spec and house file, never the note; the note is labelled a summary.
- [Hiding preferences or reviews makes the Designer forget them] → Defaults keep them; the page shows each setting's default.

## Migration Plan

One Alembic migration adding `summary_owner_edited BOOLEAN NOT NULL DEFAULT false` to `threads` and `thread_pieces`; downgrade drops both. With no `memory` key stored, behaviour is identical to today.
