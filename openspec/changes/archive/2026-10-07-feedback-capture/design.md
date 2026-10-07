## Context

See proposal.md for the motivation. What exists today:

- **Starting a render.** `run_render` is started by `plugins/render_turntable/tool.py` inside a tool node, whose `configurable` carries `trace_id` and `package_id` from `app/api/chat.py`, and by `app/api/renders.py` over HTTP.
- **Render status.** Lives in the version folder's `status.json` under `renders.<key>`, with keys from `storage.RENDER_KEYS`; `photoreal-detail` adds `detail-still` and `detail-turntable`. The file route serves `status.json`, so nothing that names a model can go there.
- **House note.** `house_note` in `app/agent/prompts.py` already composes rooms, preferences, pieces, extension requests and review items, with neutralisation.
- **Langfuse.** `Tracing` in `app/observability/langfuse.py` opens per-turn spans with tags through `propagate_attributes`. The installed SDK (`langfuse>=4.15.4`) exposes `create_score(name, value, trace_id, data_type, comment)`.
- **Predecessor.** Rated chat turns per scope and derived a bounded policy (style notes, retrieval limit). Here the thing rated is a render and personalisation goes through the house file, so only the record, the summary and the admin read are ported.

## Goals / Non-Goals

**Goals:**
- Every rating can be traced back to the render, tier, slot, model and owner request that produced it.
- Ratings reach the agents as context and the developer as evidence. They never act automatically.

**Non-Goals:**
- Automatic routing changes, prompt tuning or policy knobs derived from feedback.
- Rating chat replies or reviews. Rating renders of apartment shells (shells have no Pieces entry; possible later).
- Showing renders inside the chat page. The Pieces page is the render view.

## Decisions

1. **`render_runs` table** (migration `0008_render_feedback`): id, package_id, version, render_key, tier, started_at, finished_at, outcome (`queued|running|succeeded|failed`), thread_id, trace_id, prompt (≤ 2 000 chars, the last human message of the turn), slot, model.
   - A row is inserted where a ticket is handed to `run_render`. In the tool, the origin comes from `configurable` and the slot's routed model. In the HTTP route, the origin fields are null.
   - `run_render` gains an `on_outcome(outcome)` callback that sets finished_at and outcome.
   - Insert and update run in their own short sessions inside `try/except`, logging failures, so a database hiccup never stops a render.

   *Alternative:* store the origin in `status.json`. Rejected because the file route would expose the model to the homeowner.

2. **`render_feedback` table:** run_id (PK, FK to `render_runs`, cascade), rating (`up|down`), comment (≤ 1 000), created_at, updated_at. One row per run gives "one current rating". Re-rating is an upsert, clearing is a delete. "Latest succeeded run" for `(package, version, key)` is the newest `render_runs` row with outcome `succeeded`. A key with no such row → 409 "the render does not exist yet".

3. **Homeowner routes** (owner-gated, in `app/api/feedback.py`):
   - `GET /packages/{id}/versions/{n}/renders` lists published render keys with tier, outcome and the current rating. This is the Pieces page's data, and it omits slot, model and prompt.
   - `PUT …/renders/{key}/feedback {rating, comment?}` and `DELETE …/renders/{key}/feedback`.

   The render key is validated against `RENDER_KEYS`, and the package and version come from the path.

4. **Chat tool `record_render_feedback`** (`plugins/render_feedback/`, role `builder`, `also_for: [lighting]`, toggleable, enabled by default). It is named in the `builder.md` and `lighting.md` headers. The instruction loader refused a tool named by an agent other than its plugin's role, so the manifest gains an optional `also_for` list (built-in plugins only; never repeating an agent or naming the role). Binding stays by header, so nothing else changes. *Alternative:* two plugins with one tool each. Rejected because the homeowner would see two toggles for one action.
   - Arguments: rating, optional comment, optional render key, optional version. The package always comes from the thread's bound piece in `configurable`, never from a model argument.
   - It returns a `Confirmation` ("record 👎 'far too dark' on hall-bench v2 draft turntable?") and writes only on `yes`, matching the house-file rule that only a confirmed action writes.
   - Default target: the bound piece's most recent succeeded run.

5. **House note.** `house_note(..., role)` adds "Recent render feedback (owner's own words)" for the `designer` and `lighting` roles: up to five newest ratings on the bound piece, each line `v2 · turntable · draft · down — "doors look too thick"`, with comments neutralised like other owner text. Intake does not get it, because it does not act on renders.

6. **Langfuse.** `Tracing.record_feedback(run, rating, comment)`:
   - When `run.trace_id` is set, it calls `create_score(name="render_feedback", value=1|0, data_type="BOOLEAN", trace_id=run.trace_id, comment=comment)`.
   - It then opens a short span named `render-feedback` through the existing turn context with tags `render-feedback`, `rating:up|down`, `tier:<tier>`, and `slot:<slot>` / `model:<slug>` when known, with metadata package, version and render key.

   A re-rating adds a new score; the database holds the current value. Every call sits behind `enabled` and `_warn_once`. *Alternative:* tagging the original trace after the fact. Rejected because the SDK sets tags when a span is created, and a score is the supported way to attach feedback to an existing trace.

7. **Developer summary.**
   - `GET /admin/feedback?days=` returns rows grouped by (slot, model, tier) with up, down and the latest comment time.
   - `GET /admin/feedback/comments?slot=&model=&tier=` returns comments newest first, capped at 50.
   - The new admin page `admin/Feedback.tsx` follows `Usage.tsx`.

8. **Pieces page** (`/pieces`, linked from the main navigation). Data comes from `GET /packages`, the version route and the renders list in decision 3. The preview is `still.png` or `frames/0` from the file route. The viewer link is `viewer.html`. Thumbs are toggle buttons (shadcn `Button`), and the comment is an `Input` saved on blur or Enter. It uses TanStack Query with an optimistic update and rolls back on refusal, showing the message beside the render.

## Risks / Trade-offs

- [Prompt text stored in `render_runs` could hold personal data] → Single-owner database, the same as the checkpointer. It is never exported to the homeowner routes. Langfuse already masks e-mail addresses, and the prompt is not sent with the score.
- [Agents over-weight one comment] → Only five lines, labelled as the owner's words. They are context, not a rule.
- [Model attribution drifts when the owner re-routes a slot mid-thread] → The model is captured per run at start time, not looked up later.

## Migration Plan

`0008_render_feedback` creates both tables. Earlier renders have no run rows, so they cannot be rated until re-rendered; this is stated on the Pieces page ("rendered before ratings existed"). Rollback drops the tables. Nothing else references them.
