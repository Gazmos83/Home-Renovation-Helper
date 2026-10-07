## 1. Progress and binding (backend)

- [x] 1.1 Create `app/agent/progress.py`: move `_review_ready` and `_detail_ready` from `foreman.py` unchanged and add `piece_progress(...)` with the step rules of design.md decision 1. Verify `tests/test_progress.py` covers each step from fixtures on disk and in the house file: no piece; piece with a queued build; built with screenshot; `draft` turntable (tier read from `status.json`); review with 2 open items and with all items resolved; detail still present; a `final` job; `next_step` for each; open generator-extension requests listed; routes only, no host path in the result
- [x] 1.2 Wire the Foreman's `router` node to the shared functions. Verify `tests/test_foreman.py` passes unchanged
- [x] 1.3 Pin the existing binding with tests; no code change. Verify `tests/test_chat_api.py` covers: create on an unbound thread binds it (thread read and list); revise on an unbound thread binds it; a second created piece rebinds; an answer of `no` leaves the binding unchanged
- [x] 1.4 Add `GET /chat/threads/{thread_id}/progress` with `ProgressOut`. Verify `tests/test_chat_api.py` covers: 401 without the cookie; 404 unknown thread; 503 with the memory reason without the checkpointer; the fresh-thread scenario; the built-and-reviewed scenario; the response body contains no model slug, token figure or host path (extend the existing no-internals test)

## 2. Studio API client

- [x] 2.1 Extend `frontend/src/lib/api.ts`: `Thread` gains `created_at`/`last_turn_at`; add `thread(id)`, `sendTurn(id, message, uploadIds)`, `resume(id, confirmationId, answer, reason)`, `upload(id, file)` (multipart, no JSON header), `uploads(id)`, `progress(id)` with their types. Verify `pnpm lint` and the type check in `pnpm build` pass

## 3. Studio pages

- [x] 3.1 Rewrite `routes/Conversations.tsx` as the list (start form kept; title, piece badge, last-turn time, newest first, link to the view) and add the `/conversations/:threadId` route in `App.tsx`. Verify `Conversations.test.tsx` covers the list entry scenario and the existing start form
- [x] 3.2 Add `routes/Conversation.tsx` with `Messages`, `Composer` and the moved `Tools`. Verify `Conversation.test.tsx` covers: history rendered with the specialist's role; send disables the composer and shows the reply; a 503 shows the reason and drops the optimistic message; a 409 `confirmation_pending` refetches and shows the card; the two tool-toggle tests moved from the old file
- [x] 3.3 Add `ConfirmationCard` (subject, summary, proposal, Yes, No, reason; composer hidden while pending). Verify the test file covers Yes, No with a reason sent in the body, and reopen-while-pending
- [x] 3.4 Add upload attach to the composer (PNG/JPEG input, immediate multipart post, thumbnails on the composer and the sent message, refusal reason shown). Verify the test file covers attach-and-send carrying `upload_ids` and a 413 refusal shown with nothing attached
- [x] 3.5 Add `ProjectPanel` (piece, version and build state, step list, next step, latest screenshot or still, open requests, open-review count linking to `/pieces`; `refetchInterval` while queued or running; invalidated after turn, resume and upload). Verify the test file covers the after-first-build scenario (status flips from `running` to `succeeded` across two fetches without reload) and the open-review scenario

## 4. Verification

- [ ] 4.1 Browser check against the running backend: start a conversation from the Studio, send a brief, answer the confirmation, see the piece appear in the panel, attach one image, and render one turntable at tier `draft` through the chat; reload with a confirmation pending. Record the check in the commit message
- [x] 4.2 README: replace the `curl`-only chat walkthrough's lead-in with the Studio path, keep the `curl` section as the API reference. Verify the file reads correctly
- [x] 4.3 Run `uv run ruff check .`, `uv run pytest -m "not slow"`, and `pnpm lint && pnpm test && pnpm build`. Verify all pass and record the counts in the commit message
