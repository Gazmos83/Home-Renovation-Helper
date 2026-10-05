## Context

See proposal.md. What exists after the three earlier changes: tools as `AgentTool` objects in `app/agent/tools/*.py` with `KNOWN_TOOLS`/`all_tools()`; instruction headers naming tools; the Foreman graph binding `{t: tools[t] for t in header.tools}` and trimming history by `HISTORY_WINDOW = 40`; routing loaded once at startup with `routing:<slot>` overrides already read from `operator_settings`; `Profiles` (`generation:<slug>`, `set_generation`/`reset_generation` exist but no route); slot models built once in the lifespan; the developer gate (`require_dev`, 404 when disabled); `model_usage` rows per call with `model_id`, tokens (nullable), `operation`, `created_at` and only a project index; the Studio SPA with sign-in and pricing pages.

The predecessor's plugin system (`app/agent/plugins/`) is declarative HTTPS only, registered via the admin API into `plugin_revisions`, with `PluginExecutor` (SSRF guard via `getaddrinfo` + `is_global`, pinned IP with SNI, no redirects, 256 KiB cap, 5 s timeout, 0.5 s pacing), `tool_settings` per project and `plugin_invocations`. Its `budget.py` fits a context window with `count_tokens_approximately` × 1.2 and `trim_messages`, raising `BudgetExceeded` (`input_too_large`); it has no daily ceiling.

## Goals / Non-Goals

**Goals:**
- One manifest per plugin folder, loaded and validated at startup; ≥ 10 toggleable tools; HTTPS plugins as a fenced second kind.
- Per-thread toggles that change what a specialist binds, without touching instruction files.
- Token restrictions enforced before every call, including a daily ceiling, refused by role in plain words.
- The developer changes routing, profiles, budgets and plugins live, behind the gate, with pages.

**Non-Goals:**
- Instruction-text editing from `/admin`; plugin registration through the API; code plugins from outside the repo.
- Provider-native tokenizers; per-thread budgets; spend in money (OpenRouter's cap covers that).

## Decisions

1. **Folders, manifests, and where the code lives.** `backend/plugins/<name>/manifest.yaml` + `tool.py` (built-ins) — the tool modules move from `app/agent/tools/` into their plugin folders; `app/agent/tools/base.py` and `shared.py` stay as the framework they import. `backend/plugins/__init__.py` makes the folder a package. Manifest model (`extra="forbid"`): `name` (folder name), `description`, `kind` (`builtin|https`), `role` (`intake|designer|builder|researcher|reviewer`), `tools: [str]` (built-in: names exported by `tool.py`; https: exactly one, `plugin_<name>`), `enabled_by_default: bool`, `toggleable: bool` (default true), and for `https` the predecessor's `input_schema`/`output_schema`/`request`. *Alternative:* keep tools where they are and add manifests only; rejected because CLAUDE.md §5 defines a plugin as the folder with manifest and implementation.

2. **Loader.** `app/plugins/loader.load_plugins(root, *, allowed_hosts)` → `Plugins` (by name, tool → plugin, tools by role); errors name the manifest path. `KNOWN_TOOLS` becomes `plugins.tool_names()`; the instruction loader takes it as a parameter (header tools must be declared, and a built-in tool's role must match the header's agent). `all_tools()` becomes `plugins.builtin_tools()`.

3. **HTTPS kind ported, not re-designed.** `manifest.py`/`schema.py`/`executor.py` ported from the predecessor with `project_id` replaced by `thread_id`; manifests come from disk, so `plugin_revisions` is dropped and the revision cache is keyed by the manifest file's hash. `PLUGIN_ALLOWED_HOSTS` (default empty), `PLUGIN_TIMEOUT_SECONDS` 5.0, `PLUGIN_MAX_RESPONSE_BYTES` 262 144, `PLUGIN_MIN_INTERVAL_SECONDS` 0.5. Table `plugin_invocations` (plugin, thread_id, outcome, duration_ms, created_at). One example manifest is shipped disabled (`enabled_by_default: false`) with an `example.invalid` host in tests only, so the kind is exercised without an outbound host being allow-listed by default.

4. **Enablement.** Global: `operator_settings` key `plugin:<name>` = `on|off` (absent → `enabled_by_default`). Per thread: table `thread_tool_settings (thread_id FK CASCADE, plugin, enabled, updated_at)`, PK (thread_id, plugin). `enablement.enabled_tools(session, thread_id, role)` = (header tools ∩ tools of plugins that are globally on and (not toggleable or thread-enabled/defaulted)) ∪ enabled HTTPS tools for the role. `load_house` computes it per specialist into state (`bound_tools: {role: [names]}`) so a resumed confirmation keeps the turn's set.

5. **Budget per call.** `app/agent/budget.py` ported: `count(messages, tools)` = `count_tokens_approximately` × 1.2, each image content block counted as `IMAGE_TOKENS = 1100`. `fit(budget, system, history, tools)` keeps system + tools + current turn (from the last human message) mandatory, trims earlier history with `trim_messages(strategy="last", start_on="human")` and adds `HISTORY_OMITTED_NOTE`; raises `BudgetRefused("input_too_large", needed, usable)`. Daily: `usage.tokens_today(engine, model_id, tz)` sums `input_tokens + output_tokens` (an unrecorded figure counts the row's stored estimate — the recorder gains an `estimated_tokens` column written from the pre-call count); `needed = counted + output_cap`; over the ceiling raises `BudgetRefused("daily_limit", …)`. Called in the Foreman node, each specialist's agent node and the Reviewer's nested call, replacing `window()`.

6. **Restrictions storage.** `operator_settings` key `budget:<slug>` JSON `{context_budget_tokens, daily_token_ceiling}`; the output cap stays in `generation:<slug>` (§4: "output caps extend the existing GenerationProfile"). Defaults: context 32 000, daily 2 000 000, bounded by the registry context window. Settings `BUDGET_TIMEZONE=Europe/Berlin`.

7. **Refusal path.** `BudgetRefused` is caught in the graph node (not a `GatewayError`), so no partial state is written: the node returns a fixed AI message `"<Role> can't take this on right now: <reason in words>."` (e.g. "today's limit is reached; it resets at midnight", "the message is too long; please shorten it") and ends the turn. The reply names the role; numbers stay in the log and in Langfuse. The chat response is a normal 200 reply.

8. **Live routing and profiles.** `app.state.routing` and `app.state.models` become replaceable: `PUT /admin/routing/{slot}` probes the slug (`probe_models` for one slug, image probe for image slots), writes `routing:<slot>`, rebuilds `Routing` and the slot's model; the graph reads `model_provider` and `model_ids` through `app.state` lookups (already a dict lookup for models; `model_ids` becomes `lambda slot: app.state.routing.model_for(slot)`). Profile and budget edits rebuild the affected slot models. A lock serialises swaps; a turn already running keeps the model object it fetched.

9. **Developer routes** (`require_dev`): `GET /admin/models` (registry entries with capabilities, routing per slot with override marker, profile, restrictions, today's usage), `PUT/DELETE /admin/routing/{slot}`, `PUT/DELETE /admin/models/{slug}/generation`, `PUT/DELETE /admin/models/{slug}/budget`, `GET /admin/plugins`, `PUT /admin/plugins/{name} {enabled}`, `GET /admin/plugins/{name}/invocations`, `GET /admin/usage?days=N` (≤ 31). Homeowner routes (`require_owner`): `GET /chat/threads/{id}/tools`, `PUT /chat/threads/{id}/tools/{plugin} {enabled}` (409 for a non-toggleable or globally disabled plugin).

10. **Pages.** `routes/Conversations.tsx` (threads with toggles, plain names and descriptions only); `routes/admin/{Models,Plugins,Usage}.tsx` under `/admin/*`, mounted only after `GET /admin/models` answers 200 (a 404 hides the tree and its nav link). Component tests with mocked fetch; browser passes recorded in `tasks.md`.

## Risks / Trade-offs

- [Moving tool modules breaks imports] → One move per plugin with tests run after each; `app/agent/tools/__init__.py` re-exports during the move, removed at the end.
- [Approximate counting under- or over-estimates] → Safety factor 1.2 and the gateway's own error still caught as a `GatewayError`; the usage rows record real figures.
- [Live model swaps race a running turn] → A turn holds the model object it fetched; the lock only serialises swaps.
- [HTTPS plugins as an exfiltration path] → Allow-list empty by default, arguments validated, no secrets in arguments (ownership from the context), body never logged, global addresses only.

## Migration Plan

Migration `0006_plugins_budgets` adds `thread_tool_settings`, `plugin_invocations`, `model_usage.estimated_tokens` and an index on `model_usage(model_id, created_at)`. No existing data changes; absent settings mean manifest defaults and budget defaults. Rollback drops them.

## Open Questions

None that change the specs. Defaults recorded: context budget 32 000, daily ceiling 2 000 000 tokens per model, image cost 1 100 tokens, time zone Europe/Berlin.
