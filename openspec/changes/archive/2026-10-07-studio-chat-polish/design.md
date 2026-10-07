## Context

See proposal.md for why. The current shape this design builds on:

- A turn is one blocking `POST /chat/threads/{id}/turns` (`app/api/chat.py`) that calls `chat.answer` → `graph.invoke` and returns `TurnOut` once the graph ends or pauses. The UI (`routes/Conversation.tsx`) then refetches the thread. `TurnOut.reply` is not used by the UI.
- Pauses are `interrupt()` calls in a specialist's `tools_node` (`app/agent/foreman.py`): the first *gated* tool call of a round (an `AgentTool` with a `preview`) previews to a `Confirmation`, the payload is `{subject, summary, proposal}`, and `/resume` answers `{answer, reason}`.
- History (`chat.history`) is built from checkpointer messages. After `foreman-routing-fixes` it also shows text sent beside a tool call; this change assumes that.
- Context fitting is the pure `budget.fit`: oldest exchanges are dropped behind `HISTORY_OMITTED_NOTE`. `foreman.prompt_for` expands images (`with_images`) before fitting, so whatever the expansion adds is counted.
- Untrusted text is wrapped by `app/agent/prompts.py`; `compose_agent_prompt(text, *notes)` puts the guard last.
- `model_usage` rows carry `trace_id` and `operation` (`chat.<slot>`) but no thread. `threads` holds `title`, `package_id`, timestamps; `uploads` and `thread_tool_settings` cascade from it.
- Uploads are images only: `uploads.sniff` reads the signature; files sit at `<upload_root>/<thread>/<id>.<ext>`.
- The frontend has no Markdown renderer, no font packages and no sheet/dialog component (shadcn `ui/` holds alert, badge, button, card, input, label, select, table).

Baseline for the MODIFIED requirements: the `studio-conversation` delta specs (not yet archived). That change archives first; `openspec validate` reports the studio-ui MODIFIED header as "not found" until then.

## Goals / Non-Goals

**Goals:**
- One run path for a turn, streamed or not, so the two routes cannot drift.
- Every new model call (title, summary) metered and budgeted like a specialist's.
- No new way for model output to inject markup or reach a model slug on the homeowner view.

**Non-Goals:**
- Token-by-token streaming of reply text.
- Cancelling a running turn (a disconnected stream lets the turn finish; the checkpointer keeps the result).
- Changing routing, the ladder, the render guard or the allow-list.

## Decisions

### 1. Streaming: new `…/stream` routes beside the JSON ones, Server-Sent Events over `fetch`
`POST /chat/threads/{id}/turns/stream` and `POST /chat/threads/{id}/resume/stream` answer `text/event-stream`. Both share one generator, `chat.run_events(graph, …)`, which drives `graph.stream(input, config, stream_mode=["updates", "custom"], subgraphs=True)` and yields typed events:

| Event | Data | Source |
|---|---|---|
| `specialist` | `{role}` | the Foreman node's update carrying `specialist` |
| `tool` | `{plugin}` (plain name, `_` → space) | `get_stream_writer()` in `tools_node`, just before each bound tool runs |
| `reply` | `{reply, specialists[]}` | final state after the stream (last assistant text, roles that ran) |
| `pending` | `PendingOut` | `graph.get_state(config).interrupts` |
| `title` | `{title}` | the title step (decision 3) |
| `error` | `{failure_class, reason}` | `GatewayError` / `psycopg.OperationalError` caught inside the generator |
| `done` | `{}` | always last |

The JSON routes consume the same generator to its end and build `TurnOut` from the ending event, so behaviour and tests stay as they are. Every refusal decided before the graph runs (`_load_thread`, `_graph`, `_check_uploads`, pending 409) happens in the route before `StreamingResponse` is returned, so it keeps its HTTP status. The tracing `with tracing.turn(...)` block moves inside the generator so a streamed turn is traced exactly like a JSON one; `_forget_unanswered` runs on a gateway error exactly as now. Responses set `Cache-Control: no-cache` and `X-Accel-Buffering: no`; the Vite proxy already forwards `/chat`.

The browser cannot `EventSource` a POST, so `lib/api.ts` gets `streamTurn(threadId, body, onEvent)` reading `response.body` with a small SSE line parser (no dependency).

*Alternatives:* replacing the JSON routes (breaks the README `curl` walkthrough and every chat API test for no gain); WebSocket (bidirectional machinery for a one-way feed); polling a progress registry (needs in-process state keyed by turn and still lags).

### 2. `ask_owner`: a second kind of pending item on the existing interrupt
A new plugin `backend/plugins/ask_owner/` (role Intake and Designer, not toggleable) defines `AgentTool(name="ask_owner", preview=…, run=…)`. Its preview validates the questions (1–8; text 1–200; unit ≤ 20; choices 2–8 of 1–60) and returns a new `Questions` preview type beside `Confirmation`; being gated, it already obeys "first gated call of the round wins, the rest are not run". `tools_node` interrupts with `{"kind": "questions", "questions": [...]}` for it and `{"kind": "confirmation", subject, summary, proposal}` otherwise. `chat.Pending` and `PendingOut` gain `kind` and `questions`; existing fields are empty for a question set.

`ResumeIn` becomes `{confirmation_id, answer?, reason?, answers?, declined?}` with a validator: a confirmation needs `answer`; a question set needs exactly one of `answers` (same length as the questions, each 1–500 characters) or `declined` (1–2000). The old body shape stays valid. The resume value reaches `run`, which returns the answers as a numbered "question → answer" text (or the declined message) as the tool result, and the specialist continues in the same turn.

History: an `ask_owner` call and its tool result are shown as one `MessageOut(role="assistant", kind="answers", rows=[{question, answer}])`; ordinary messages get `kind="text"`. The UI renders `answers` as the Question | Answer table.

*Alternatives:* free text with "?" parsing in the browser (fragile, rejected by the owner); ending the turn and taking answers as a normal message (loses the pairing of question and answer, and the specialist starts a new turn cold).

### 3. Titles: a Foreman-slot call after the first answered turn, written only into an empty title
After a turn ends without failure on a thread whose title is empty, `app/agent/titles.py` asks the Foreman slot's model (no tools, low output cap of 24 tokens) for a 3–6 word title of the owner's first message, through `budget.prepare` and the usage recorder with operation `chat.title`. The result is trimmed to 200 characters, delimiters neutralised, and stored with `UPDATE threads SET title = :t WHERE id = :id AND title = ''`, so an owner rename that lands first wins. On `BudgetRefused`, `GatewayError` or an empty answer the fallback is the first message cut at a word boundary to ≤ 60 characters. The streamed route emits `title` after the ending event and before `done`; the JSON route does the same work before answering (one extra short call, once per thread). `ThreadIn.title` stays optional; the start form sends none. `PATCH /chat/threads/{id}` takes `{title}` (1–200 characters after trimming).

*Alternative:* code-only title from the first words (cheaper; the owner chose the model).

### 4. Delete: checkpointer first, then the index row and files
Built by `piece-versions-and-chat-delete` (its design decision 5), which refuses a delete while a turn runs instead of letting the turn finish into a discarded thread. Kept here for the summary and usage notes.

`DELETE /chat/threads/{id}` → `checkpointer.delete_thread("chat:<id>")` (fails → 503 memory reason, nothing else touched), then delete the `threads` row (cascades `uploads`, `thread_tool_settings`), then remove `<upload_root>/<id>/`. `model_usage.thread_id` is `ON DELETE SET NULL`, so spend stays. Pieces, versions, rooms and reviews are keyed by package or room, not thread, and are untouched. A turn still running on the thread finishes into a checkpointer thread nobody reads; `touch_thread` on a missing row becomes a no-op instead of an error.

### 5. Text notes: a third upload kind, expanded for every slot
`uploads.sniff` is unchanged for images; a new `classify(head, rest)` returns `text` when the bytes are not an image, decode as UTF-8 and hold no control characters but `\t\n\r`. Text opening with `{` or `[` stays the design file's: it is a design or it is refused with 415, as design-import already specifies (owner decision 2026-10-07). Notes have their own cap, `UPLOAD_MAX_NOTE_BYTES` (default 256 KiB), checked while streaming the file as images are. Stored as `<id>.md`, served `text/plain; charset=utf-8` with `nosniff`. In `foreman.prompt_for`, the expansion step (renamed `with_attachments`) appends each note to the owner's message as a delimited untrusted block labelled with its original name, for every slot whether image-capable or not; it runs before `prepare`, so the note is counted. The front end's file input accepts `image/png,image/jpeg,.md,.txt,text/markdown,text/plain`. The conflict table is an Intake instruction (decision 8), backed by a prompt test.

### 6. Summaries replace the shortened-history note
`budget.fit` gains an optional `summarize: Callable[[list[BaseMessage]], str | None]`. When history must be trimmed, `fit` computes the dropped prefix as now, calls `summarize(dropped)`, and if text comes back and fits in the space the note would have used plus the freed budget, sends it as a `SystemMessage` holding the summary inside the untrusted delimiters, labelled "summary of earlier conversation"; otherwise it sends `HISTORY_OMITTED_NOTE` as today. `fit` stays pure given the callback.

`foreman.prompt_for` passes a `summarize` bound to the thread: `app/agent/summaries.py` reads `threads.summary` / `summary_through` (the id of the last message covered). If the stored summary covers the whole dropped prefix it is returned without a call. Otherwise one Foreman-slot call (operation `chat.summary`, output cap 400 tokens, its own `prepare` with *no* summarize callback, so it cannot recurse) condenses *the stored summary plus only the newly dropped messages* into "decisions so far: rooms and figures confirmed, pieces and versions, open questions", and the result is written back. Any refusal or failure returns `None`. The checkpointer messages are never modified.

*Alternatives:* LangGraph's `SummarizationNode` (rewrites state; the spec requires the stored conversation unchanged); summarising on every turn (spends tokens on short threads).

### 7. Thread on usage rows and the developer calls page
`model_usage.thread_id` (nullable, FK `threads.id ON DELETE SET NULL`). `UsageRecorder` takes it from `configurable["chat_thread"]`. `GET /admin/threads/{id}/calls` (developer gate) returns rows newest first with `slot` derived from `operation` (`chat.designer` → `designer`), model slug, tokens, `estimated` flag. Studio page `routes/admin/ConversationCalls.tsx` at `/admin/conversations` (thread picker → calls), linked only from the admin nav.

### 8. Prompt notes composed in code
`app/agent/prompts.py` gets `FORMATTING_NOTE` (bullets for questions, tables for item lists and decisions, `calc` fences for arithmetic, "structured questions go through `ask_owner` when you have it"). `specialist_graph.agent` appends it to every specialist's notes, so `compose_agent_prompt` places it after the editable text and before the guard. The note-conflict rule is a line in `instructions/intake.md` (it is behaviour of Intake, not a fixed note); `instructions/intake.md` and `designer.md` headers add `ask_owner`.

### 9. Rendering replies
`components/chat/Reply.tsx` uses `react-markdown` with `remark-gfm` and **no** `rehype-raw`, so raw HTML stays text. `components.code` turns a `language-calc` block into a `<figure>` with a 2 px border; `components.img` renders only `src` beginning with `/packages/`, `/apartments/` or `/uploads/`, otherwise its alt text; a link (written or a bare route) is kept only when it is a piece, composition or shell file route, opening in a new tab with `rel="noreferrer noopener"`; any other address, including `https://`, is shown as plain text (the existing render-route rule from `studio-conversation`). Owner messages stay plain text with `whitespace-pre-wrap`. Tables reuse `ui/table.tsx` styling.

### 10. Layout, fonts, rail
Fonts from `@fontsource/commissioner` (400, 600) and `@fontsource/oswald` (500) imported in `main.tsx`; Tailwind v4 `@theme` tokens `--font-chat` and `--font-heading`. Chat text uses `font-chat leading-relaxed` with `space-y-3` between blocks. Headings use Oswald on every page through one base rule in `index.css` (`h1, h2, h3 { font-family: var(--font-heading) }`), so homeowner and `/admin` pages change together with no per-page edit (owner decision 2026-10-07); speaker names use the same token. Body text outside the chat keeps the current font. Bubbles: `max-w-[80%]`, owner `ml-auto` with accent background, replies `mr-auto` bordered; forms `mx-auto`. The rail is a 48 px column with two `Button variant="ghost"` icons (`Wrench`, `Ruler` from lucide); the flyout is an absolutely positioned `section` with `role="dialog"`, closed by Escape, by its close button or by the icon, focus moved into it on open and back on close. No new UI dependency.

### 11. Help page
Static `routes/Help.tsx` at `/help`, in the main nav. Content mirrors the `studio-ui` requirement and the Intake rules (`record_brief` / `record_plan` fields), with a worked example drawing of one room.

## Risks / Trade-offs

- [Proxy or browser buffers the stream, so events arrive all at once] → `X-Accel-Buffering: no`, no compression on the route, a Vitest for the parser and a browser check through the Vite dev proxy.
- [Sync generator inside `StreamingResponse` holds a threadpool worker for the whole turn] → same cost as today's blocking route; single user, one worker.
- [A client that disconnects mid-turn sees nothing] → the turn completes and the checkpointer holds it; reopening the thread shows the reply or the pending card.
- [Summary invents or drops a decision] → it is labelled and delimited as untrusted, the house file (rooms, brief, pieces, reviews) stays the factual source in every prompt, and the developer can read the summary call on the calls page.
- [Title or summary calls spend the Foreman's daily ceiling] → small output caps (24 / 400 tokens); refusal falls back without failing the turn.
- [Markdown renderer as an XSS path] → no raw HTML, image source allow-list, a test with an `onerror` payload.
- [`ask_owner` overused for single questions] → the formatting note says to use it when two or more figures are missing; one question may stay in text.
- [Migration number collides with another change applied in between] → take the next free revision at apply time.

## Migration Plan

One Alembic revision: `threads.summary TEXT NULL`, `threads.summary_through VARCHAR(64) NULL`, `model_usage.thread_id UUID NULL REFERENCES threads(id) ON DELETE SET NULL` with an index, and widen the `uploads.kind` check (if any) to admit `text`. All additive; downgrade drops them. Existing threads keep their titles; existing usage rows have no thread. Rollback: revert the code and downgrade one revision.

## Open Questions

