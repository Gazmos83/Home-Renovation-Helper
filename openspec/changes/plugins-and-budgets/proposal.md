## Why

The agents' tools are hard-wired, every slot's model and limits are set only in files, and nothing stops a long thread or a busy day from spending tokens without bound. CLAUDE.md §5 makes every tool a plugin with a manifest the homeowner can toggle, keeps the predecessor's declarative HTTPS plugins as a second kind, and §4 gives the developer panel per-agent model routing and per-model token restrictions — enforced in code before the call, never by the model. This is §11 step 7, and it carries the deferred general web lookups: an HTTPS plugin on an allow-listed host.

## What Changes

- **Plugins as folders**: each tool group moves to `backend/plugins/<name>/` with a `manifest.yaml` (name, description, the agent role it serves, its tools, enabled by default, toggleable) and its implementation; the backend loads the manifests at startup and refuses a malformed one by file name. Built-ins: `intake` (`record_brief`, `record_plan`; not toggleable), `create_piece` (not toggleable), `revise_package`, `cut_list`, `room_fit`, `guidelines`, `blender_build` (`blender_build`, `build_shell`), `render_turntable`, `material_cost` (`price_cut_list`, `manage_remnants`), `catalog_research` (`search_catalog_knowledge`, `check_live_listing`, `compare_products`), `revision_review` — ten toggleable tools.
- **Declarative HTTPS plugins** (second kind, ported): a manifest with an input schema, an output schema and one GET request to an allow-listed https host; executed with the predecessor's SSRF guard (global addresses only, no redirects, pinned IP with SNI), pacing, timeout and response cap; the result wrapped as untrusted content; every call audited without its body. No HTTPS plugin ships enabled.
- **Homeowner toggles per thread**: each conversation has its own on/off set, defaulting from the manifests; a specialist binds the tools its instruction header names that are enabled for the thread, plus enabled HTTPS plugins for its role. A turn never binds a disabled tool.
- **Token restrictions per registry model** (admin): maximum output tokens per call (the generation profile's cap), a context budget per turn, and a daily token ceiling. A budget step before every model call counts the request (characters-based approximation with a safety factor, images at a fixed cost), trims the oldest history to fit the context budget (replacing the 40-message window), refuses a request whose mandatory part does not fit, and refuses a call that would pass the day's ceiling. The Foreman states the refusal to the homeowner by role, never by model.
- **Developer panel** (dev-gated routes and pages): per-slot model routing to a registry entry that passes the gateway probe (no fallback; the change applies without a restart), each model's generation profile and token restrictions, plugins enabled or disabled globally with their recent invocations, and token usage per model per day.
- **Studio pages**: a conversations page with each thread's tool toggles (homeowner, no models or tokens shown), and the developer panel's pages on a separate route tree that only appears when the panel is enabled. Each page gets a browser pass.
- **Not included**: editing instruction text from `/admin` (later), `photoreal_detail` (step 8), feedback (step 9), plugins registered through the API (manifests are checked-in files).

**Ladder step and agent:** no ladder step changes. Agents: all — tool binding and the budget apply to the Foreman and every specialist. **Render guard:** not affected (`render_turntable` keeps its guard path; toggling it off removes the tool, never the guard). **bpy allow-list:** not affected.

## Capabilities

### New Capabilities
- `plugins`: plugin manifests, built-in and HTTPS kinds, loading, the HTTPS executor and its guards, invocation audit, global and per-thread enablement.
- `token-budget`: per-model token restrictions, counting and trimming before every call, the daily ceiling, and how a refusal reaches the homeowner.
- `dev-panel`: the developer routes for routing, generation profiles, token restrictions, plugins and usage.

### Modified Capabilities
- `design-agents`: a specialist binds only enabled tools; the instruction loader's known tools come from the manifests.
- `homeowner-chat`: a turn is bounded by the token budget instead of a message window; threads carry tool toggles.
- `llm-gateway`: generation profiles are edited from the developer panel and applied without a restart.
- `studio-ui`: conversations with tool toggles, and the developer panel pages.

## Impact

- Code: `backend/plugins/<name>/{manifest.yaml,tool.py}` (tool modules moved from `app/agent/tools/`, which keeps `base.py`/`shared.py`), `app/plugins/{manifest,loader,https_schema,executor,binding,enablement}.py`, `app/agent/budget.py`, `app/agent/foreman.py` (binding and budget per call), `app/agent/instructions/__init__.py` (known tools from manifests), `app/api/{tool_toggles,admin_models,admin_plugins,admin_usage}.py`, `main.py` (plugin load, live routing swap), migration `0006_plugins_budgets` (`thread_tool_settings`, `plugin_invocations`, `model_usage(model_id, created_at)` index).
- Settings: `PLUGIN_ALLOWED_HOSTS`, plugin timeout, response cap and pacing; the day boundary time zone (`Europe/Berlin`).
- Frontend: `routes/Conversations.tsx` (toggles), `routes/admin/{Models,Plugins,Usage}.tsx`.
- Tests: manifest validation per field, the HTTPS executor (SSRF, redirect, size, timeout, revocation), toggles per thread reaching binding, budget counting/trimming/refusals, daily ceiling across turns, routing change probed and applied live, dev gate 404, no model or token in homeowner responses, component tests and browser passes.
- Depends on the three earlier changes for the tools it wraps.
