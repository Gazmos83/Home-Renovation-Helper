No task in this change renders; the guard and the allow-list are untouched. Archive `studio-conversation` before this change; `foreman-routing-fixes` must be applied first.

## 1. Schema and storage

- [ ] 1.1 Add the Alembic revision of design.md "Migration Plan" (next free number): `threads.summary`, `threads.summary_through`, `model_usage.thread_id` (FK `ON DELETE SET NULL`, indexed), `uploads.kind` admitting `text`; update `app/db/models.py`. Verify a migration test upgrades and downgrades cleanly and that deleting a thread nulls its usage rows' `thread_id`
- [ ] 1.2 `house_file`: `set_title(session, id, title)`, `set_title_if_empty(...)` (conditional update), `read_summary` / `write_summary` (`delete_thread` and the `touch_thread` no-op come from `piece-versions-and-chat-delete`). Verify `tests/test_house_file.py` covers the conditional title and that deleting a thread also removes its summary

## 2. Uploads: text notes

- [ ] 2.1 `app/agent/uploads.py`: `classify` for `text` (UTF-8, no control characters but tab/LF/CR), `UPLOAD_MAX_NOTE_BYTES` setting (default 256 KiB, in `config.py` and `.env.example`), stored as `<id>.md`, served `text/plain; charset=utf-8` with `nosniff`. Verify `tests/test_uploads*.py` covers the Markdown note, a ZIP named `.md` (415), an oversized note (413, no partial file), and the served content type
- [ ] 2.2 Rename `with_images` to `with_attachments` in `foreman.py` and append each note to the owner's message as a delimited untrusted block named by its file name, for every slot. Verify tests cover: Intake and the Builder both receive the note text inside the delimiters; a note with "ignore your instructions" stays inside them; the budget count rises with the note's size

## 3. Turn runner and streaming

- [ ] 3.1 Extract `chat.run_events(...)` (design decision 1) used by `answer` and `resume`; emit `tool` events through `get_stream_writer()` in `tools_node`; keep `TurnResult` for the JSON path. Verify `tests/test_chat.py` and `tests/test_foreman.py` pass unchanged and a new test asserts the event order for a Foreman → Designer → `revise_package` turn
- [ ] 3.2 Add `POST /chat/threads/{id}/turns/stream` and `/resume/stream` (`text/event-stream`, no-cache, no buffering), tracing inside the generator, `_forget_unanswered` on a gateway error. Verify `tests/test_chat_api.py` covers: the followed-turn scenario; 409 while pending opens no stream; 401/404/422/503 before streaming; a gateway timeout ends with an `error` event and the thread holds no unanswered message; no event body contains a model slug, token figure, tool argument or host path

## 4. Titles and rename

- [ ] 4.1 `app/agent/titles.py` (design decision 3) wired after a successful first turn on both routes, `title` event on the stream. Verify tests cover the generated title (fake model), the daily-ceiling fallback to ≤ 60 characters at a word boundary, an owner rename landing first being kept, and a usage row with operation `chat.title`
- [ ] 4.2 `PATCH /chat/threads/{id}` (404 unknown); `DELETE` comes from `piece-versions-and-chat-delete`. Verify `tests/test_chat_api.py` covers the rename scenarios from the homeowner-chat delta

## 5. Questions through `ask_owner`

- [ ] 5.1 Add `backend/plugins/ask_owner/` (manifest: Intake and Designer, not toggleable) with the `Questions` preview; extend the interrupt payload with `kind`, `Pending`/`PendingOut` with `kind` and `questions`; add `ask_owner` to the `intake.md` and `designer.md` headers. Verify `tests/test_plugin_manifest.py` and a new `tests/test_ask_owner.py` cover a valid set pausing, nine questions refused to the model, and an `ask_owner` call after a gated call in the same round not run
- [ ] 5.2 Extend `ResumeIn` (answers / declined, old body still valid) and the run that returns answers to the specialist; history shows an `answers` entry with rows. Verify `tests/test_chat_api.py` covers the answered, wrong-count (422, still pending), declined and stale-id (409) scenarios, and that an old-shape confirmation answer still works

## 6. Prompts and summaries

- [ ] 6.1 Add `FORMATTING_NOTE` to `app/agent/prompts.py` and append it for every specialist; add the note-conflict rule to `instructions/intake.md`. Verify `tests/test_prompts.py` / `tests/test_instructions.py` assert the note appears once, after the editable text and before the guard, survives an edited instruction, and that Intake's text carries the conflict-table rule
- [ ] 6.2 Add the `summarize` callback to `budget.fit` and `app/agent/summaries.py` (design decision 6), bound in `prompt_for`. Verify `tests/test_budget.py` covers summary used, summary reused with no call, refusal falling back to the note, and the summary call itself never recursing; and a Foreman test shows the stored checkpointer messages unchanged after a summarised call

## 7. Developer calls

- [ ] 7.1 Record `thread_id` in `UsageRecorder`; add `GET /admin/threads/{id}/calls` behind the developer gate. Verify `tests/test_admin_*` covers the three-row first-turn scenario (foreman, intake, foreman title), 404 unknown thread, 404 with the panel disabled, and that no homeowner response gains a slug

## 8. Studio

- [ ] 8.1 Add `react-markdown`, `remark-gfm`, `@fontsource/commissioner`, `@fontsource/oswald` with `pnpm add`; font tokens, the global `h1, h2, h3` Oswald rule and chat spacing in `index.css`. Verify `pnpm build` passes, the built CSS references only bundled font files (no Google URL), and contains the heading rule; the browser check (9.1) confirms Oswald headings on one homeowner page outside the chat (Pieces) and one `/admin` page
- [ ] 8.2 `lib/api.ts`: `streamTurn`/`streamResume` with an SSE parser, `renameThread`, `threadCalls` (`deleteThread` comes from `piece-versions-and-chat-delete`), new `Pending`/`Message` types. Verify a Vitest feeds chunked SSE text split mid-line and gets each event once, in order
- [ ] 8.3 Split `routes/Conversation.tsx` into `components/chat/` (`Reply` with Markdown, `calc` box and image allow-list; `Bubble`; `WaitingBubble`; `Composer` with remove-before-send and note attachments; `QuestionForm`; `Rail` with flyouts). Verify `Conversation.test.tsx` covers: send-and-read with the waiting bubble naming Foreman then Intake and the specialists listed under the reply; refused turn; table in a reply; calc box; HTML shown literally; removed-before-send carrying only the note; two questions one at a time and the Question | Answer table; choice buttons; reopened with questions pending; rail open/close/switch and Escape; rename in place; title event updating the heading; the moved tool-toggle and project tests still passing
- [ ] 8.4 `routes/Conversations.tsx`: one-click start without a title, keeping the delete action from `piece-versions-and-chat-delete`. Verify `Conversations.test.tsx` covers start-without-title and its delete tests still pass
- [ ] 8.5 `routes/Help.tsx` at `/help` in the nav, and `routes/admin/ConversationCalls.tsx` at `/admin/conversations` in the admin nav only. Verify Vitest checks the help page lists every measurement in the studio-ui requirement and the calls page renders rows with slot and slug

## 9. Verification

- [ ] 9.1 Browser check against the running backend through the Vite dev proxy: start a conversation without a title, send a message and watch the waiting bubble change specialist, see the generated title, answer an `ask_owner` form, attach and remove an image, attach a `.md` note, open and close both flyouts, rename, open the developer calls page, and confirm headings on the Pieces page and one `/admin` page are set in Oswald. No render is started. Record the check in the commit message
- [ ] 9.2 README: streamed routes, rename/delete, text notes and the help page in the chat section. Verify the file reads correctly
- [ ] 9.3 Run `uv run ruff check .`, `uv run pytest -m "not slow"`, and `pnpm lint && pnpm test && pnpm build`. Verify all pass and record the counts in the commit message
