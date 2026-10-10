## 1. Langfuse

- [x] 1.1 Owner step: create an EU Langfuse Cloud project and set `LANGFUSE_HOST=https://cloud.langfuse.com`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` in `.env`; restart the backend. Verify one chat turn shows up as a trace in Langfuse with the owner, session and slot.

- [x] 1.2 Expose `trace_url(trace_id)` on the tracing wrapper (null when tracing is off); add `trace_url` to each `CallOut` and a `tracing` flag to the calls response. Verify the dev-panel scenarios "Trace link shown" and "Tracing off", and a test that no developer response contains either Langfuse key.

## 2. Database

- [x] 2.1 Alembic migration for `model_prices` and `guideline_uploads`, with models in `db/models.py`. Verify `uv run alembic upgrade head` and `downgrade -1` both run on the test database.

## 3. Prices

- [x] 3.1 Admin routes: `GET /admin/model-prices` and `POST /admin/model-prices/refresh` (one OpenRouter `/models` request, registry slugs only, per-million `Decimal`, `fetched_at`; failure keeps stored rows). Verify "Prices refreshed", "Slug not priced" and "Refresh fails" with a mocked HTTP transport, and the developer gate (404 / 401).

- [x] 3.2 Models page: price columns, fetch date, "Refresh prices" button, "no price" text. Verify with Vitest, and "Homeowner never sees prices" with a test over the homeowner routes.

## 4. Call graphs

- [x] 4.1 `GET /admin/usage/summary?days=7|30|90`: totals per model, per day (budget time zone) and per slot, with estimated cost and a cost-incomplete flag. Verify "Totals per agent", "Unpriced model" and "Range refused".

- [x] 4.2 `pnpm add recharts`; Calls page: range picker, metric toggle (calls / tokens / cost), three bar charts above the existing table; trace link column; tracing state line. Verify with Vitest (charts render from mocked data, links open the trace URL in a new tab) and `pnpm build`.

## 5. Workflow map

- [x] 5.1 `GET /admin/workflow`: nodes and edges from the compiled Foreman graph and sub-graphs, routed slug per agent, plugins with global state, and markers from one annotation table (`interrupt()` and render-guard nodes). Verify "Map matches routing", "Disabled plugin", "Guard visible", and a test that every annotated node exists in the compiled graph.

- [x] 5.2 `/admin/workflow` page and nav link: layered SVG (homeowner → Foreman → agents → plugins) with model labels and markers. Verify with Vitest and a browser look at the page.

  Done 2026-10-10: the owner reports all dev-panel-insights tasks complete.

## 6. Guideline PDF upload

- [x] 6.1 `load_sources` returns checked-in plus uploaded sources; `GUIDELINE_UPLOAD_MAX_BYTES` setting; admin routes to upload (magic bytes, size, readable text, duplicate sha256), list with ingestion state, re-ingest, and delete (uploaded only). Verify every design-guidelines scenario in this change, and that `python -m app.ingestion --guidelines` ingests an uploaded source.

- [x] 6.2 `/admin/guidelines` page and nav link: upload form (title, jurisdiction, published on, licence), source list with state, re-ingest and delete. Verify with Vitest and one manual upload of a real PDF in the browser.

## 7. Design rules and open items

- [x] 7.1 `load_rules` merges `design_rule:<id>` overrides over the YAML with startup validation; an invalid stored override is skipped and reported, not fatal. Admin routes to list (source: file or page, valid or not), save, reset and delete, swapping `app.state.design_rules` on success. Verify the design-guidelines scenarios "Rule added from the panel", "Rule without a source refused", "Rule reset to the file", "Invalid override does not stop startup", and that with no overrides the table equals the YAML.

- [x] 7.2 `GET /admin/open-items` scanning for `TODO(user)`. Verify "Open owner items listed" against a temporary file tree.

- [x] 7.3 `/admin/rules` page and nav link: rule list with source and origin, add and edit form (check chosen from the closed set, parameters for that check, severity, source picked from publications and owner notes), reset and delete; open-items list. Verify with Vitest and a browser check.

## 8. Checks

- [x] 8.1 Backend: `uv run ruff check .`, `uv run pytest -m "not slow"`. Frontend: `pnpm lint`, `pnpm test`, `pnpm build`. All must pass. No render is run by this change (no tier).

- [x] 8.2 Owner check in the browser: Calls graphs over 7 days, one trace link opening in Langfuse, prices on the Models page after a refresh, the workflow map, one PDF uploaded and found by the Designer through `search_guidelines`, and one rule added on `/admin/rules` (e.g. the shelf-span limit asked for in `partial-and-folded-dividers` task 0.2) taking effect without a restart. Record the owner's verdict in this change.
