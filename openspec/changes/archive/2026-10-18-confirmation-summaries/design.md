## Context

See proposal.md (Why). The current state:

- `Confirmation(subject, summary, proposal)` (`backend/app/agent/tools/base.py:182`) is returned by every gated tool's preview. Subjects are internal names (`compose_room`, `revise`, `create_piece`, …; 17 call sites under `backend/plugins/`).
- When the owner answers, `foreman.py` (around line 1340) stores `{subject, summary, answer, reason}` on the gated call's `ToolMessage.additional_kwargs["confirmation"]`. No model sees these kwargs.
- `chat.history` turns that record into `{"role": "confirmation", "text": _confirmation_line(...)}`, i.e. "subject: summary — answer (reason)" (`chat.py:523-580`). `MessageOut` has only `text` for it.
- The pending card (`ConfirmationCard`, `Conversation.tsx:398-417`) shows "Confirm: {pending.subject}". The answered entry is a `<p>` "Answered: {m.text}" (`Conversation.tsx:986-991`).
- `compositions.propose` (`backend/app/compositions.py:349-418`) builds the summary lines from `stored["items"]` and `stored["resolved"]["items"]` (`size_mm`, `centre_mm`, `rotation_deg`, and `base_mm` for ceiling items once `composition-ceiling-layer` lands).

## Goals / Non-Goals

**Goals:**
- One place maps subjects to plain titles, used by the history and the pending card alike.
- The room change's table uses the numbers the checks computed.
- Old threads keep working: their entries get a title from the stored subject, and no table.

**Non-Goals:**
- Tables for confirmations other than `compose_room`. The summary text stays their body. Others can add a `table` later.
- New calculations (gaps between items, distances to other walls).
- Changing what any model sees.

## Decisions

1. **Titles in the backend, not the frontend.** `chat.CONFIRMATION_TITLES: dict[str, str]` with the 17 subjects from the proposal, and `confirmation_title(subject)`, which returns "Confirmation" for an unknown subject. Both the history entry and `PendingOut` carry `title`. The frontend only displays it.
   - *Why not map in the frontend:* the no-internals rule is a backend contract (`homeowner-chat`), and tests there can check every subject.
   - A test collects every `Confirmation(subject="…")` literal under `backend/plugins/` and asserts each has a title, so a new tool without a title fails.

2. **`table` is an optional, typed field on `Confirmation`.** `table: dict | None = None`, shaped `{"columns": [str], "rows": [[str]]}`. The cells are display strings formatted by the producer (`"1200 × 600 × 800"`, `"wall 2, 400 mm"`, `"free, 90°"`), so the frontend never formats millimetres.
   - The answered record in `foreman.py` adds `"table": outcome.table` when set.
   - `_pending_of` and `chat.Pending` pass it through.
   - Putting the table inside `proposal` was rejected: `proposal` is the tool's structured data and is not shown as-is.

3. **The composition table.** `compositions.propose` builds the rows in the same loop that writes the summary lines, from `stored["items"]` plus `sizes_by_id` and the resolved `centre_mm` / `rotation_deg` / `base_mm`.
   - Columns: Item, Kind, Size (mm), Placement, Centre (mm), Rotation, plus "Hangs at (mm)" only when an item is on the ceiling layer.
   - `Proposal.table` is passed by `compose_room.preview` into `Confirmation(table=…)`.
   - The summary text is unchanged, so what the model gets back from the tool is unchanged.

4. **History entry shape.** `MessageOut` for `role == "confirmation"` gains `title`, `answer` (`"yes"`/`"no"`), `reason` (nullable), `summary` and `table` (nullable). They are left out when absent, following the existing `exclude_if` pattern. `text` stays the old line, so nothing that reads `text` breaks.
   - The existing history test changes only by the new keys.

5. **Collapsed row in the frontend.** A new `AnsweredConfirmation` component in `Conversation.tsx` replaces the paragraph:
   - `<div data-role="confirmation">` with the title, " · Yes/No", and "— reason" when there is one;
   - an outline `size="sm"` button with a chevron (`aria-expanded`, accessible name "Show details of <title>");
   - when open, the `<pre>` summary and a `Table` built like `AnswersTable`.
   
   Local state only, so a reload starts collapsed. Compact layout rules (left-aligned) already apply through `data-role`.

## Risks / Trade-offs

- Old answered compose confirmations have no table, which is accepted (scenario "answered before titles existed").
- If `composition-ceiling-layer` has not landed when this is applied, the "Hangs at" column is left out. The task notes the dependency.
- Long tables in a narrow chat column: the table sits in an `overflow-x-auto` wrapper.
