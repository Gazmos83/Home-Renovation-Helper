## 1. Settings

- [x] 1.1 `MemorySettings` model (defaults = today's constants, ranges per the dev-panel spec) stored under `operator_settings` key `memory`; read helper with fallback. Verify unit tests: absent key gives today's values; each out-of-range value is refused naming the field.

- [x] 1.2 Admin routes `GET/PUT /admin/memory` and per-field reset, behind the developer gate, returning defaults and the fixed-rules list. Verify the dev-panel scenarios "Trigger lowered", "Out of range", "Reset", "Panel disabled".

## 2. Compression

- [x] 2.1 Migration: `summary_owner_edited` on `threads` and `thread_pieces`. Verify `alembic upgrade head` and `downgrade -1`.

- [x] 2.2 `budget.fit`: trigger share, kept turns, and note-covered exchanges replaced even when they fit. Verify the token-budget scenarios "Earlier trigger", "Recent turns kept", and "Defaults unchanged" (requests byte-equal to today's for a recorded long thread), plus every existing budget test.

- [x] 2.3 `summaries`: note length, editable instructions plus the fixed tail, tool-result cut, owner-edited base on refresh. Verify "Owner correction survives a refresh" and that the fixed tail is present whatever the editable text says.

- [x] 2.4 `POST /chat/threads/{id}/note/compress` (owner gate; refused while a turn runs). Verify "Compress now" and "Compression refused", and that the response holds no token figure or model name.

## 3. Note panel

- [x] 3.1 Owner routes to read and save the active note (neutralised, capped, marked owner-edited). Verify the homeowner-chat scenarios "Note shown", "No note yet", "Owner edits the note", "Delimiter in an edited note", "Without a login".

- [x] 3.2 "Decisions so far" panel beside the chat with edit, save and "compress now". Verify with Vitest (no token, model or cost text in the panel) and a browser check.

  Done 2026-10-10: the owner marked 3.2, 4.2 and 5.1 complete.

## 4. House file

- [x] 4.1 Slice options in `prompts.py` (other builds, preferences, review items, rating count, extension requests). Verify "Other builds hidden", "Fewer ratings", and that every existing house-file slice test passes with defaults.

- [x] 4.2 Save options: review confirmation through the existing confirmation flow; preferences skipped when off. Verify "Review waits for confirmation", "Preferences not saved", "Extension requests always saved".

  Done 2026-10-10: preferences skipped when off, extension requests always saved (both tested). Open: review confirmation. A tool's confirmation is asked before it runs, but the review's model call happens inside the run, so "confirm after the review finishes" needs either a pending-review state (a column on reviews, a confirm action, and the slice reading only confirmed reviews) or a spec change to "ask before the review runs and is saved". Marked complete by the owner 2026-10-10 without a choice recorded: review confirmation is not built. The `reviews` setting is stored but has no effect yet and is hidden on `/admin/memory`.

## 5. Developer page

- [x] 5.1 `/admin/memory` page and nav link: grouped settings with defaults, reset per field, and the fixed-rules list. Verify with Vitest and a browser check.

## 6. Checks

- [x] 6.1 Backend `uv run ruff check .`, `uv run pytest -m "not slow"`; frontend `pnpm lint`, `pnpm test`, `pnpm build`. All must pass. No render is run by this change (no tier).

- [x] 6.2 Owner check: in a long conversation, open "Decisions so far", correct one line, press "compress now", and confirm the next reply uses the correction. Change one `/admin/memory` setting and see it apply without a restart. Record the owner's verdict in this change.

  2026-10-10: the owner's first try failed, "compress now" answered "could not be compressed now". Cause: the Foreman's model (a reasoning alias) spent the whole 400-token note cap on hidden reasoning and returned empty text; a live call with a long transcript gave 0 characters at 400 tokens. Fix: side calls (notes, titles) send `reasoning: disabled`; the same call then returned an 866-character note in 227 tokens. Retested and passed: the owner marked it complete 2026-10-10.
