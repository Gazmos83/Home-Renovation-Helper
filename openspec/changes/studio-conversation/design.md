## Context

See proposal.md for the motivation. What exists today:

- **Chat routes.** `app/api/chat.py` starts, lists and reads threads, runs a turn (`POST …/turns`) and answers a confirmation (`POST …/resume`). A turn is synchronous: the response is the reply. `read_thread` already opens the checkpointer snapshot for messages and the pending interrupt. Uploads are `POST /chat/threads/{id}/uploads` (multipart) and `GET /uploads/{id}`.
- **Turn result.** `app/agent/chat.TurnResult` carries reply, specialist, pending and failure. `create_piece` and `revise_package` bind the thread themselves (`touch_thread(..., package_id=…)` inside the confirmed action), and the Foreman prefers `thread.package_id` over the graph state.
- **Progress facts.** `app/agent/foreman.py` computes per turn: the bound piece from `thread.package_id` or state, `house_file.pieces()` (latest version, folder status), `_review_ready` (screenshot, still or first frame exists), `_detail_ready` (succeeded build with `model.blend`), `latest_open_items`. Render tiers per key live in the version's `status.json` under `renders.<key>.tier` (`storage.RENDER_KEYS`: `still`, `turntable`, `room-*`, `detail-*`). `app/api/feedback.describe_renders` already turns those into homeowner-safe items with package routes.
- **Studio.** `frontend/src/routes/Conversations.tsx` is one page: a title form and, per thread, the tool toggles. `api.ts` has `threads`, `createThread`, `tools`, `setTool` only. The `Thread` type lacks `created_at` and `last_turn_at`, which the backend already returns. Pages use TanStack Query, shadcn `Button`/`Input`/`Badge`, `cardClass`, `FieldError` from `lib/form.tsx`, and Vitest with a stubbed `fetch`.

## Goals / Non-Goals

**Goals:**
- One place in the backend that answers "how far is this piece" for both the Foreman and the Studio, so the panel and the agents never disagree.
- The Studio talks to the existing chat routes as they are; the only new route is the progress read.
- Nothing in any homeowner response names a model, prompt, token, cost or path.

**Non-Goals:**
- Streaming replies or a progress bar for a running turn. A turn stays one request; the composer waits.
- Starting builds, renders or reviews from buttons. Every action still goes through the Foreman in words, so the guard and the confirmations stay where they are.
- Rendering the turntable viewer inside the chat. The panel links to the viewer and a reply's file route is a link (decision 8); the viewer opens in its own tab.
- Apartment shells in the panel. The thread's piece is a furniture package; shells keep their own routes.

## Decisions

1. **A shared progress module, `app/agent/progress.py`.** Move `_review_ready` and `_detail_ready` out of `foreman.py` unchanged and add `piece_progress(session, root, package_id, brief_confirmed) -> dict` that returns: `package_id`, `name`, `latest_version`, `build_status`, `steps` (an ordered list of `{step, done, detail}` for `brief`, `piece`, `built`, `rendered`, `reviewed`, `detail`, `final`), `next_step`, `open_review_items`, `open_requests` (`field`, `request`), `screenshot` and `still` as package routes or null. The Foreman's `router` node calls the same functions for `piece_ready`, `review_ready` and `detail_ready`; its prompt text does not change.
   - *Why not derive in the Studio from `/packages` and `/reviews`?* Three round trips and a second copy of the rules. The Foreman already encodes them; the Studio should read, not re-derive.
   - *Why not store a "stage" column?* The steps are facts on disk and in tables; a stored stage would drift (a build can fail, a review can be dismissed).
   - *Step rules.* `brief`: the thread's `brief` state or the piece's recorded brief. `piece`: a version exists. `built`: latest version status `succeeded`. `rendered`: `still` or `turntable` job on the latest version with tier `draft` or `preview`; detail says which tier. `reviewed`: a review exists for the latest version; detail is the open count. `detail`: `detail-still` or `detail-turntable` exists. `final`: any job on the latest version with tier `final`. `next_step` is the first step not done, phrased for the owner ("ask for a draft render").
2. **Route `GET /chat/threads/{id}/progress`** in `app/api/chat.py`, owner-gated like the rest. It reads `brief` from the checkpointer snapshot (same `graph.get_state` as `read_thread`; a missing graph answers 503 with the memory reason as the other reads do) and the rest from the house file and the folder. Response model `ProgressOut` with explicit fields so nothing extra leaks, same guard as the other chat models.
   - *Why a separate route and not a field on `read_thread`?* The panel refreshes on its own cadence while a build runs; the message history should not be re-read every few seconds.
3. **Binding stays where it is.** The tools bind inside the confirmed action, in the same transaction as the piece record, so a failed or declined action binds nothing and the Foreman's preference for the thread's piece keeps later turns on the piece just worked on. No code changes; tests pin the behaviour (create on an unbound thread, revise on an unbound thread, create of a second piece rebinding, a declined or failed turn binding nothing).
   - *Why not bind from the turn result?* It would duplicate what the tools do and could disagree with them.
4. **Studio routes.** `/conversations` lists threads (title, piece badge, relative last-turn time) and keeps the start form; `/conversations/:threadId` is the view. The view is one component file `routes/Conversation.tsx` with four parts: `Messages`, `Composer` (with upload attach), `ConfirmationCard`, `ProjectPanel`; `Tools` moves there unchanged. Queries: `["thread", id]` (detail), `["progress", id]` with `refetchInterval` of 3 s while `build_status` is `queued` or `running`, and invalidated after every turn, resume and upload. The list query gains `created_at`/`last_turn_at` on the `Thread` type.
5. **Composer behaviour.** Sending appends the owner's message optimistically; on an `ApiError` the optimistic message is removed and the error's reason is shown with `FieldError`, matching the spec's "not kept in the list". A 409 `confirmation_pending` refetches the thread so the card appears. The composer is hidden while `pending` is set and disabled while a mutation is in flight.
6. **Uploads.** A file input accepts `image/png,image/jpeg`; each file is posted at once as multipart (no JSON header; a dedicated `api.upload` that bypasses the JSON `request` helper's content type) and its `upload_id` is kept in composer state until the next send. Thumbnails use `/uploads/{id}`. Refusals (413, 415, 422) show the service's reason under the input.
7. **Browser check.** The Studio spec requires a recorded browser check per page before it counts as done; the tasks keep that, with one fixture piece and a tier `draft` turntable.

## Risks / Trade-offs

- [The optimistic message is removed on a model-gateway failure, but the service also forgets the unanswered message, so the two agree; if a future failure class keeps the message server-side, the view would hide it until reload] → the view refetches the thread after any error, so the server's history wins.
- [Polling the progress route while a build runs costs one folder read every 3 s] → the read is a few `stat` calls and a short query; polling stops as soon as the status leaves `queued`/`running`.
- [Moving `_review_ready`/`_detail_ready` touches the Foreman] → pure extraction with the existing Foreman tests unchanged; the new module's tests cover the step rules directly.

## Decision added after the browser check (2026-10-07)

8. **The turntable is reachable from the view.** The first run of task 4.1 found no way to open a finished turntable: the reply named `/packages/<id>/versions/<n>/files/viewer.html` as plain text, which reads like a file path, and the panel showed only the screenshot.
   - *Progress.* `piece_progress` gains `viewer`: the package route of the latest version's `viewer.html` when its turntable is published (the same check `describe_renders` uses: `frames/frame_000.png` and `viewer.html`), else null. The picture prefers the still over the screenshot once a still exists, so a render replaces the blockout picture.
   - *Panel.* When `viewer` is set the panel shows "Open the turntable viewer" opening in a new tab, as the Pieces page does.
   - *Replies.* In a reply's text, a route of the form `/packages/…/files/…`, `/compositions/…/files/…` or `/apartments/…/files/…` is rendered as a link that opens in a new tab; a trailing full stop is not part of the link. Only these three prefixes are linked, so a reply cannot point the owner anywhere else. The tool's reply text stays as it is; the Builder's words are unchanged.
   - *Frames by file name.* The viewer loads `frames/frame_<nnn>.png` relative to itself. The package, shell and composition files routes serve that name as well as `frames/<n>`, so a viewer opened through the app finds its frames.
   - *Files on a sent message.* The thread history names the uploads sent with an owner's message (`upload_ids`, left out when none were), so the thumbnail stays on the message after the reply.
