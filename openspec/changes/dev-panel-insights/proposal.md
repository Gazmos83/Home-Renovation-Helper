## Why

The owner's App Check (`docs/App Check_2 09-10-2026.md`) found the developer panel hard to read. Calls are plain tables with no totals per agent or any trend, Langfuse traces are not reachable even though every call row stores its trace id, nobody can see how the agents hand work to each other, model prices are invisible so spend cannot be judged, and guideline PDFs can only be added from the command line.

## What Changes

1. **Langfuse turned on and linked.** The owner creates a Langfuse Cloud project in the EU region and sets `LANGFUSE_HOST=https://cloud.langfuse.com`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` in `.env` (tracing code is already in place and stays optional). The Calls page shows whether tracing is on, and each call row with a trace id links to its Langfuse trace. No keys or secrets reach the browser; only the trace URL does.
2. **Graphs on the Calls page.** Above the per-conversation table, bar charts of calls, tokens and estimated cost **per model**, **per day** and **per agent** (slot), with a 7 / 30 / 90-day range. Built from the existing `model_usage` table; no migration for this part. Charts use `recharts` (new frontend dependency).
3. **Agent workflow map.** A new `/admin/workflow` page shows a static diagram: the homeowner, the Foreman, each specialist agent with its routed model and its enabled plugins, the hand-offs between them, and where the render guard and `interrupt()` confirmations sit. Nodes and edges come from the compiled LangGraph and the plugin manifests, so the map cannot drift from the code.
4. **Model prices.** The Models page shows each registry slug's input and output price per million tokens, fetched from OpenRouter's public model list with a "refresh prices" action and the fetch date. A slug the list does not price (for example the `~deepseek/deepseek-v4-flash-latest` alias, if absent) shows "no price", never a guess. Stored prices drive the estimated cost on the Calls page, marked "estimate at the last fetched price".
5. **Guideline PDF upload.** A new `/admin/guidelines` page uploads a PDF with title, jurisdiction, publication date and licence note. The file is saved under the gitignored `docs/guidelines/pdf/`, recorded, and ingested into the corpus at once. The page lists uploaded and checked-in sources with their ingestion state, and deletes an uploaded one (file and passages). The checked-in source list and the CLI keep working as before.
6. **Design rules and open owner items.** A new `/admin/rules` page:
   - **Rules**: lists every design rule (check, values, severity, quoted source) and lets the developer add a rule or edit one. A rule names a check from the closed set in `guidelines/checks.py` and must cite a source: a listed publication or an owner note (`owner:<note id>`). Rules are validated exactly as at startup. Edits are stored in the database on top of `config/design_rules.yaml`, apply from the next check without a restart, and each can be reset to the file's version; a rule added on the page can be deleted.
   - **Open items**: a read-only list of every `TODO(user)` marker in the backend code and config, with its file, line and text, so decisions waiting on the owner are visible.

Not **BREAKING**. Everything is on the developer route; the homeowner view never shows models, tokens, costs or prices.

**Ladder step:** none (no furniture spec or generator change). **Agents:** no agent's prompt, tools or model changes. The Designer's `search_guidelines` sees uploaded PDFs as ordinary `guideline` passages. **Render guard:** not affected. **bpy allow-list:** not affected.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `dev-panel`: call graphs and Langfuse links, the workflow map, model prices with estimated cost, and the open `TODO(user)` list.
- `design-guidelines` (also): design rules can be added and edited from the developer panel, stored over the checked-in table.
- `design-guidelines`: guideline PDFs can also be uploaded from the developer panel, beside the checked-in source list.

## Impact

- Backend: `backend/app/api/admin_threads.py` (trace URL per call, usage aggregates per model/day/slot with cost), a new admin route for prices (OpenRouter `GET /api/v1/models`, one call on refresh), a new admin route for the workflow map, a new admin route for guideline uploads, new admin routes for design rules (`guidelines/rules.py` merges stored overrides over the YAML and reloads `app.state.design_rules`) and for the `TODO(user)` list; `backend/app/guidelines/ingest.py` and `sources.py` read uploaded sources too; `backend/app/observability/langfuse.py` exposes the trace URL.
- Database: one Alembic migration adding `model_prices` (slug, input and output price per million tokens, fetched at) and `guideline_uploads` (id, title, jurisdiction, published on, licence, file name, sha256, size, ingested at, error).
- Frontend: `recharts` added with pnpm; `routes/admin/ConversationCalls.tsx`, `routes/admin/Models.tsx`, new `routes/admin/Workflow.tsx`, `routes/admin/Guidelines.tsx` and `routes/admin/Rules.tsx`, links in `App.tsx`, `lib/api.ts`.
- Config: `.env.example` notes the EU host. The owner adds the Langfuse keys; no secret is committed.
- Rule overrides are stored in `operator_settings` (keys `design_rule:<id>`), so they need no table.
- Tests: backend route tests (gate, aggregates, prices, uploads, workflow, rules, open items), Vitest for each page.
