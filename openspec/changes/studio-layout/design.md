## Context

See proposal.md for why. The current shape this design builds on:

- The header is `<header className="border-b bg-card">` in `frontend/src/App.tsx` (nav links in `links` and `adminLinks`). It scrolls away with the page.
- Every page sits in `components/Page.tsx`: `mx-auto max-w-5xl px-4 py-8`. The conversation route (`routes/Conversation.tsx`) puts the rail and the messages in a `relative flex` inside it.
- `components/chat/Rail.tsx` is a `w-12` column of icon buttons (Wrench for Tools, Ruler for Project). The label is only in `aria-label`. The flyout is `absolute top-0 left-14` over the chat. The open panel id is state in `Conversation.tsx`.
- `ProjectPanel` (in `Conversation.tsx`) refetches progress every 3 s only while `build_status` is `queued` or `running`. It shows "Open the turntable viewer" from `progress.viewer` and "Inspect version N" as an underlined `Link` to `/pieces/<id>/versions/<n>`.
- Render status is kept per render key in the version's `status.json` (`runner.mark_render_queued`, then the runner's own updates). `app/agent/progress.py` reads `renders` only to decide what is done.
- A conversation render starts in `plugins/render_turntable/tool.py` `run` (and `plugins/photoreal_detail/tool.py` for a detail pass) with `asyncio.run_coroutine_threadsafe(runner.run_render(...))`. `run_render` calls `on_outcome("succeeded" | "failed")` once at the end; today it only closes the feedback run. `ctx.thread_id` is known in the tool. `app/api/renders.py` starts Studio renders with no thread.
- A thread's messages live in the LangGraph checkpointer; `chat.history` turns them into `MessageOut` entries. The `threads` row is the index; uploads and tool settings cascade from it.
- `routes/PieceInspector.tsx` holds the whole inspector body (query of the version and its spec, tabs, camera, modes, layers, `InspectorCanvas` lazy-loaded with `Suspense`) inside `<Page>`.
- "Open the … viewer" links also sit on `routes/Pieces.tsx` (per render) and `routes/Rooms.tsx` (per composition). `viewer.html` is written by the generators and by render offload.
- `render_turntable.run` replies "Started a {tier} {kind} of {label} version {n}: {estimate}. When it finishes it will be at {route}." (`viewer_route`); `render_detail` in `photoreal_detail/tool.py` replies the same way with `_files_route`. `builder.md` says to tell the owner "where the viewer will be" and `lighting.md` "where it will appear".

## Goals / Non-Goals

**Goals:**
- The notice comes from code at the moment the render ends, never from a model.
- One inspector component for the page and the split view, so they cannot drift.
- No change to what a render produces, how it is guarded, or what the Reviewer sees.

**Non-Goals:**
- Push to the browser (WebSocket or a long-lived stream). Polling, as the panel does today, is enough for one owner.
- A notice inside the model's context. The Foreman already reads progress facts every turn.
- An inspector for compositions or shells.
- Changing what `builder.md` and `lighting.md` say beyond the one line that follows the new reply.

## Decisions

### 1. Notices are rows in a new `thread_notices` table, merged into history by position
Table `thread_notices`: `id`, `thread_id` (FK to `threads`, `ON DELETE CASCADE`), `created_at`, `after_messages` (int), `outcome` (`succeeded` / `failed`), `tier`, `text`, `package_id` (nullable), `version` (nullable). `after_messages` is the number of messages in the thread's checkpointed state when the notice is written. `chat.history` walks the messages as now and inserts each notice once its `after_messages` messages have been passed (notices with the same count keep their `created_at` order). `MessageOut` gains `role: "notice"` with `outcome`, `tier`, `package_id` and `version`, left out for other entries.

`package_id` and `version` are set only for a piece record (alone, in a room, or a detail pass). The frontend shows the Review button only when both are set and the outcome is `succeeded`.

*Alternatives:* appending an `AIMessage` with `graph.update_state` (puts the notice in every later model call, and a write while a turn runs on the same thread forks the checkpoint); ordering by time (checkpointed messages carry no timestamp).

### 2. Posted from `on_outcome`, by the tool that started the render
In `render_turntable.run` and `photoreal_detail.run`, the `on_outcome` lambda calls the feedback run's `finish_run` as now and then `notices.post(deps, thread_id, quote, outcome)` when `ctx.thread_id` is set. `post` builds the text from the quote (tier, kind, record, package id or shell / composition label, version, detail or not), reads the message count with `graph.get_state` for `chat:<thread>`, and inserts the row. It never raises: any error (thread gone, checkpointer down) is logged and dropped, so a render's outcome is never changed. If the thread row is missing, nothing is written. `app/api/renders.py` passes no thread and posts nothing.

Text, built in code only (no error text, no paths):
- succeeded, piece: "The {tier} {kind} of {package} version {n} is ready. You can also check it in the Project panel."
- succeeded, detail pass: "The {tier} detail {kind} of {package} version {n} is ready. …" (same second sentence).
- succeeded, shell or composition: "The {tier} {kind} of {label} version {n} is ready."
- failed: "The {tier} {kind} of {label} version {n} did not finish, so nothing new was published. You can ask for it again."

*Alternative:* a hook inside `runner.run_render` (the runner does not know threads, and `app/api/renders.py` would need to opt out).

### 3. The browser follows a render through progress
`progress.piece_progress` gains `rendering: bool`, true when any render job of the latest version is `queued` or `running` in `status.json`. `ProjectPanel` refetches every 3 s while `build_status` is queued/running **or** `rendering` is true. The conversation's thread query uses the same interval while `rendering` is true, and is invalidated once when `rendering` turns false, so the notice appears. A shell or composition render is not in the bound piece's progress, so its notice shows after the next turn or a reload; this is stated, not hidden.

The progress query moves from `ProjectPanel` up to `Conversation` (same query key) so it runs whether or not the Project flyout is open.

### 4. Review button label names the tier
`` `Review ${tier} ` + (version === 1 ? "v1" : `revision ${version}`) `` with `tier` one of `draft`, `preview`, `final`: "Review draft v1", "Review preview revision 2", "Review final revision 3" (owner's decision, 2026-10-08). The notice row therefore also stores `tier`, and `MessageOut` carries it for a notice.

### 4a. The render reply points at the chat, not the viewer
`render_turntable` and `render_detail` no longer put a route in their reply. For a piece version (alone, in a room, or a detail pass) it ends "When it finishes, a Review button appears in this chat."; for a shell or composition, which get a notice with no button, "When it finishes, a notice appears in this chat." The estimate and the "no longer approved" note stay. `viewer_route` and `_files_route` are dropped where nothing else uses them. `builder.md`'s line "…and where the viewer will be" becomes "…and what the tool says will appear in this chat when it finishes"; `lighting.md`'s "tell the owner where it will appear" becomes "tell the owner it will appear in this chat". Both stay within "never promise to tell the owner later": the notice is code's, stated by the tool, not a promise of the model. The chat still links any file route a reply happens to contain (studio-ui, unchanged).

### 5. Split view state lives in the address
`/conversations/:threadId?inspect=<package-id>/<n>`. The Review button and the panel's Inspect button set it (`useSearchParams`, replace the history entry); the close control removes it. On `lg` and wider the conversation area becomes two columns of equal width (chat, inspector); below `lg` the inspector follows the chat. The inspector column is `sticky` below the header with its own scroll, so the chat scrolls independently. The `Page` component gains a `wide` prop (`max-w-none`) used only by the conversation route; every other page is unchanged.

*Alternative:* local state (lost on reload, which the spec forbids); a nested route (the inspector page already owns `/pieces/...`).

### 6. One `InspectorView` component
`components/inspector/InspectorView.tsx` takes `packageId` and `version` and holds everything `PieceInspector` renders inside its card today (queries, tabs, controls, canvas, straight-on views). `routes/PieceInspector.tsx` keeps its `Page`, back link and heading and renders `InspectorView`. The split view renders it with a heading, a close button and a smaller canvas height (`h-[50vh]`). `InspectorCanvas` stays lazy, so a conversation that never opens the inspector does not load three.js.

### 7. Sticky header and the pinned rail
Header: `sticky top-0 z-40` with its existing background, so content scrolls under it. Its height is exposed as a CSS variable `--header-h` (set on `:root` in `index.css`, matching the header's fixed height) for the rail and the inspector to sit below it.

Rail: the conversation route's outer layout becomes `flex` at full width: the rail is `sticky top-[var(--header-h)] h-[calc(100vh-var(--header-h))] shrink-0 border-r` at the screen's left edge, then the conversation area. Collapsed width stays `w-12`; expanded is about `w-36` with the label beside each icon. The expand control is a button at the rail's foot with `aria-expanded` and the name "Show labels" / "Hide labels" (ChevronsRight / ChevronsLeft icons, from `lucide-react`, already a dependency). The flyout keeps its behaviour and is placed beside the rail's current width.

The expanded state is remembered in `localStorage` under `studio.rail.expanded`, each read and write in `try`/`catch`, collapsed when nothing can be read. `TODO(user)`: assumed acceptable as a per-browser convenience (owner said it is fine).

### 8. Inspect becomes a button
`<Button type="button" variant="outline">` that sets the `inspect` parameter. `rounded-md` plus the border give the framed, rounded look; no new style.

### 9. Viewer links removed for pieces; `viewer.html` still written
The links go from `Conversation.tsx` and `Pieces.tsx`. `Rooms.tsx` keeps "Open the turntable viewer of <composition>" for now, because compositions have no inspector (owner's decision, 2026-10-08); it goes once compositions get one. The `viewer` fields stay in the API responses (progress, piece renders, compositions), unused by the Studio, so no API or spec of the service changes. Generators, `app/render/viewer.py`, render offload and the Reviewer are untouched. This is the minimal choice and the recommended one: dropping `viewer.html` would touch four writers and two specs for no gain, and the file stays useful to open by hand.

## Risks / Trade-offs

- [Notice placed before the end of a reply still being written] → `after_messages` is read when the render ends; if a turn is running then, the notice comes before that turn's new messages. Acceptable: it is true at the time it was posted.
- [Polling while a long final runs] → 3 s on two small reads, only while a render runs; the same as builds today.
- [Checkpointer read from the event loop in `on_outcome`] → one `get_state` per render end; wrapped so a failure only loses the notice.
- [Two columns too narrow on a 13-inch screen] → the chat column keeps a minimum width; below `lg` the layout stacks.
- [Sticky header covers anchors or the flyout] → offsets use `--header-h`; the flyout's `max-h` is reduced by it; checked in the browser pass.

## Migration Plan

One Alembic revision (next free number at apply time; `0013_chat_polish` is the latest today): create `thread_notices` with the FK to `threads` (`ON DELETE CASCADE`) and an index on `(thread_id, after_messages)`. Downgrade drops the table. No data to move. Roll back the backend and the frontend together: an older Studio does not know the `notice` role.

## Open Questions

Decided by the owner on 2026-10-08:
- The Rooms page keeps "Open the turntable viewer of <composition>", because compositions have no inspector; it is kept until they get one (decision 9).
- The render reply no longer gives the viewer route; it says a Review button (or a notice) appears in this chat (decision 4a).
- The Review button names the tier (decision 4).
- The owner chose the automatic notice (option C), so the design-agents requirement "No specialist promises to report back after the turn" is modified: specialists still never promise or send a later message; the code-posted render notice is the one exception.

- `TODO(user)`: notices for shell and composition renders carry no button and point nowhere, since neither has an inspector or a Project panel entry.
