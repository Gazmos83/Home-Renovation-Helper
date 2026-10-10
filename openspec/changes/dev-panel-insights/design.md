## Context

See proposal.md for the motivation. Already in place: `model_usage` stores model, operation (mapped to a slot by `slot_of` in `api/admin_threads.py`), tokens or estimate, thread and Langfuse `trace_id` per call. `observability/langfuse.py` runs tracing only when host and both keys are set. The installed Langfuse SDK (4.17) has `Langfuse.get_trace_url(trace_id=…)`. The Foreman graph is built with `StateGraph` in `agent/foreman.py`; plugin manifests are loaded at startup; `interrupt()` sits in `agent/foreman.py` and the render guard in `render/guard.py` / `render/guard_node.py`. Guideline sources come from the checked-in `backend/config/guideline_sources.yaml`, ingested by `python -m app.ingestion --guidelines` from files under `docs/guidelines/` (the `pdf/` folder is gitignored). The frontend has no chart library.

## Goals / Non-Goals

**Goals:**
- Read the panel's numbers at a glance, with costs that are honest about being estimates.
- Keep every new view derived from the code or the database, so it cannot drift.

**Non-Goals:**
- Embedding the Langfuse UI, or reading data back from Langfuse's API.
- Billing-accurate cost (OpenRouter's own dashboard and spend cap stay the authority).
- Uploading Markdown or URL guideline sources from the panel; the YAML list still covers those.
- A per-turn live trace diagram (Langfuse covers that through the per-call link).

## Decisions

1. **Trace URL built server-side with the SDK.** `get_trace_url(trace_id=…)` on the existing client gives the right project path for the EU host without configuring a project id. The calls route adds `trace_url` per row; when tracing is off it is null and a `tracing` flag is false. Alternative, a hand-built URL from a `LANGFUSE_PROJECT_ID` setting, rejected: one more setting that can be wrong.

2. **Aggregates from SQL, one route.** `GET /admin/usage/summary?days=7|30|90` returns three groupings (model, day in `BUDGET_TIMEZONE`, slot via `slot_of`) with calls, input, output, estimated-token calls and cost. A `Literal[7, 30, 90]` refuses other ranges by name. The existing `/admin/usage` route and page stay as they are.

3. **`recharts` for the charts.** Small, React-native, works with Tailwind colours; three bar charts with a metric toggle (calls / tokens / cost). Hand-drawn SVG was offered and declined.

4. **Prices in a `model_prices` table, refreshed on demand.** One `GET https://openrouter.ai/api/v1/models` through the existing OpenRouter client's base URL and an `httpx` call with the key header, on the developer's "refresh" only, never at startup or per call. OpenRouter states `pricing.prompt` and `pricing.completion` in dollars per token as strings; they are stored as `Decimal` per million tokens, with `fetched_at`. Only registry slugs are kept. A slug missing from the list, or an alias the list does not name, stores no row and shows "no price". Cost = (input × input price + output × output price) / 1 000 000; estimated-token calls are costed at the input price and marked. Alternative, a hand-typed price in `models.yaml`, was offered and declined.

5. **Workflow map from the compiled graph plus an annotation table.** The route reads `graph.get_graph()` nodes and edges from the Foreman graph and each specialist sub-graph, joins each agent to its routed slug (`routing`) and its plugins (manifests plus global state), and adds markers from one small code table naming the nodes that `interrupt()` and the nodes behind the render guard. A test fails when that table names a node the graph no longer has. The frontend draws it as a fixed layered layout (homeowner → Foreman → agents → plugins) in SVG; the graph is small, so no layout library. LangGraph's Mermaid PNG export was rejected: it calls an external renderer.

6. **Uploaded guideline sources in a `guideline_uploads` table.** The YAML stays the checked-in list. `load_sources` returns YAML sources plus uploaded rows (id `upload-<short sha>`), so the CLI and the panel ingest the same set. Upload checks: `%PDF-` magic bytes, size up to a new `GUIDELINE_UPLOAD_MAX_BYTES` (default 50 MB), `pypdf` must extract some text, and sha256 must be new. The file is written as `pdf/upload-<sha12>.pdf` under the guideline root (gitignored), then ingested in the request; an ingestion failure keeps the row with its error so it can be re-ingested. Delete removes the chunks (`replace_page_chunks` with none), the file and the row. Text extraction runs in the request; a large PDF may take some seconds, which is acceptable on a single-user developer route.

7. **Rule edits as overrides in `operator_settings`.** Keys `design_rule:<id>` hold a rule's full JSON, in the same shape as a YAML entry. `load_rules` builds the table from the YAML, then applies stored overrides (replace by id, or add when the id is new) and validates the merged table with the same checks as startup: known check, parameters that check takes, a source naming a listed publication or an existing owner note, at most one rule per bracket check. A rejected save names the rule and field and leaves the running table unchanged. A successful save swaps `app.state.design_rules`, so the next check uses it without a restart. Reset deletes the override and so restores the file's version; a page-added rule is deleted the same way. If startup finds a stored override that no longer validates (for example its note was deleted), the override is skipped with a logged warning naming it, and the page marks it invalid, rather than stopping the service. The YAML is never rewritten, so its comments and git history stay intact. Writing back to the YAML was offered and declined.

8. **`TODO(user)` list scanned on request.** The route scans `backend/app`, `backend/plugins` and `backend/config` (not tests, not `.venv`) for the literal `TODO(user)` and returns file, line and the rest of that line. It is read-only and capped at 200 items. Files are read from the checked-out tree, so the list follows the code without a registry to maintain.

## Risks / Trade-offs

- [A page-edited rule silently weakens a limit] → Every rule shows its quoted source and whether it comes from the file or the page; reset is one click.

- [OpenRouter changes its price format or omits the alias] → Parse strictly; an unparsable price is "no price" with the reason logged, never zero.
- [Estimated cost misread as the bill] → Every cost label says "estimate at the last fetched price"; the OpenRouter spend cap remains the real limit.
- [Uploaded PDF carries an injection] → Passages go through the same chunk delimiters as all retrieved text (CLAUDE.md §8); nothing in the PDF is executed.
- [Workflow annotations drift] → A test that every annotated node exists in the compiled graph.
- [Langfuse keys leak to the browser] → Only the URL string is returned; a route test asserts no key appears in any developer response.

## Migration Plan

One Alembic migration creating `model_prices` and `guideline_uploads`; downgrade drops both (uploaded files are left on disk, listed in the downgrade's log line). The owner then creates an EU Langfuse Cloud project and sets `LANGFUSE_HOST=https://cloud.langfuse.com`, `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in `.env`, then restarts the backend.
