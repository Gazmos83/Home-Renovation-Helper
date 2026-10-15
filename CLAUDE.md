# CLAUDE.md — Home Renovation Agents

Single-user personal project: design custom furniture and room layouts for the owner's own home, model them in Blender, render cheap turntables, review them against the brief, and price the build from lawful supplier data. Portfolio-quality code; no multi-tenant concerns.
This file is the "what". [docs/DESIGN_NOTES.md](docs/DESIGN_NOTES.md) is the "why". Acceptance scenarios live in `openspec/specs/`; active changes in `openspec/changes/`.
The code base is a pruned port of `/home/pingu/Applications/Interior_Design_App` (§7). Course requirements are in `docs/Task requirements.md`.
Status: the Reviewer lands with `render-reviewer` (2026-10-06); the detail pass with `photoreal-detail`; render feedback with `feedback-capture`. Pricing remains a later step.

## 0. OpenSpec workflow (mandatory)

Every product change is proposed before it is built. Schema `spec-driven`, skills in `.claude/skills/`, CLI `openspec`.
Explore → propose (`openspec new change "<kebab-name>"`, then `proposal.md`, delta specs, `design.md`, `tasks.md`) → stop → apply only on an explicit request, ticking `tasks.md` as each behaviour lands → archive and sync specs.
Read-only investigation, questions and work on a change already named in the conversation need no new change. Skip the workflow only when the user says so.

## 1. Hard rules

- **No Blender render without the render guard** (§6). Enforced in code, including tests. Headless jobs and live-socket work both pass through it.
- **The spec JSON is the source of truth.** Dimensions, parts, materials, cut list and prices derive from it. Nothing at ladder step 3 writes a dimension back.
- **The three-step ladder** (§3) is the order of escalation: spec change → generator extension → live Blender. Live MCP is step 3 only.
- **Eevee by default.** Cycles only for the `final` tier after a typed approval.
- **Viewport screenshots, not renders, for progress checks.**
- **Validate every agent-produced JSON against the spec schema before Blender sees it;** unknown fields are refused by name and become a generator-extension request, never a bpy fallback.
- **Every live `bpy` script goes through the allow-list** (§8) before the socket.
- **Homeowner UI and developer settings on separate routes.** The homeowner view never shows models, prompts, tokens or costs.
- **One cheap model per agent, no backup.** No automatic fallback; a slot's model is changed only by hand from `/admin`, and only to a registry entry the gateway probe has passed.
- **Token restrictions are enforced in code,** never by the model (§4).
- **Prices come only from lawful sources** (§5a). A 403 is an answer. Never switch identity to defeat a refusal.
- Ask the user when a decision is not covered here; mark assumptions `TODO(user)`.

## 2. Environment

| Item | Value |
|---|---|
| Hardware | Dell XPS 13, Linux, CPU only. Rendering is the bottleneck, not tokens |
| Blender | 5.2.1 LTS at `/home/pingu/Applications/blender-5.2.1-linux-x64/blender`; pin it, run the `--blender` suite before changing |
| Headless path | `blender --background --python <generator> -- --spec … --out …`, one process at a time (`asyncio.Semaphore(1)`) |
| Live path | Blender MCP addon, JSON over TCP on `localhost:9876`, direct socket client from the backend; step 3 only; refused while a headless job holds the semaphore |
| Backend | Python 3.14, FastAPI, Pydantic, SQLAlchemy, Alembic, LangGraph, uv (`uv add`, `uv run`; commit `uv.lock`) |
| Frontend | Vite + React + TypeScript SPA, Tailwind + shadcn/ui, TanStack Query, React Router, Vitest, pnpm. No Next.js, no SSR |
| LLM gateway | OpenRouter only, one key, `ChatOpenAI` with the OpenRouter base URL; spend cap set in the OpenRouter dashboard |
| Observability | Langfuse callback with user/session/project IDs; outages log and continue |
| Store | PostgreSQL + pgvector; app tables, checkpointer and vectors in one database; local `BAAI/bge-m3` embeddings (1024) |
| Memory | LangGraph Postgres checkpointer per thread; long-term **house file** (§9a) |
| Render server | Optional: a rented GPU box reached with the system `ssh` (key only, pinned host key); runs `final` Cycles renders only, chosen from `/admin/offload`, never a fallback; off unless `RENDER_OFFLOAD_*` are set (§6). Either a fixed host the owner starts and stops, or a RunPod pod the app creates from a network volume after approval and deletes when idle (10 min default; `docs/runpod-setup.md`) |
| Render output | `docs/renders/<package-id>/<version>/` holding `frames/`, `still.png`, `viewer.html`; contents gitignored, folder kept |

Blender 5.x: read the Eevee engine identifier from `bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items` (5.2 uses `BLENDER_EEVEE`); auto smooth is the Smooth by Angle modifier; look shader nodes up by type.

## 3. Architecture

One **Foreman** supervisor graph; specialists are LangGraph sub-graphs with their own tools and model. The homeowner talks only to the Foreman.

```
Homeowner ⇄ Foreman (routing, house file)
             ├─ Intake      → brief → confirmed numbers (room, heights, style, budget)
             ├─ Designer    → spec JSON; create / revise packages; cut list; room fit
             ├─ Builder     → validate → headless generator → screenshots → turntable (guard)
             ├─ Lighting & materials → photoreal detail pass over the socket (step 3, guard)
             ├─ Reviewer    → render + spec vs brief → discrepancy list (no write tool)
             └─ Researcher  → toom live data, price list, catalog RAG, web lookups, plugins
```

**Apartment shells are in scope.** Intake reads blueprints and room photos with a vision model into the house file's room polygons, heights and openings; the Builder generates the shell headless at step 1 from that data (port of the apartment-render skill's `generate_shell.py`); camera matching against photos and Cycles finals are step 3 and `final` tier.

**Ladder.** 1) *Spec change*: Designer revises, user confirms, Builder renders headless in about half a minute. 2) *Generator extension*: a change the schema cannot express is refused by field name; the bot records a generator-extension request in the house file, and the schema and generator grow through an OpenSpec change. 3) *Live Blender*: one-off work on the generated `model.blend` — detail pass, look-dev, camera match, inspection — saved as renders or attachments on that version.
Flow for a new piece: Intake → confirm → Designer → confirm → Builder blockout → screenshot → OK → guard (draft) → Reviewer → iterate → optional step 3 → guard (`final`, approval).

## 4. Agents and model routing

Routing lives in `config/models.yaml`: one registry entry per agent, no backup. The registry refuses unknown slugs at startup and at selection. Prices and benchmark notes below are from 2026-10-05 (OpenRouter list, Artificial Analysis index); re-verify before first run.

| Agent | Model | Reason |
|---|---|---|
| Foreman | `~deepseek/deepseek-v4-flash-latest` | the predecessor's model family; alias by the owner's decision of 2026-10-09 |
| Intake | `deepseek/deepseek-v4.1-flash` | reads blueprints and room photos, so it needs image input (decided 2026-10-06); same model as the Reviewer |
| Designer | `~deepseek/deepseek-v4-flash-latest` | the predecessor's model family; alias by the owner's decision of 2026-10-09 |
| Builder | `deepseek/deepseek-v4-pro-0813` | bpy is well-trodden; allow-list and schema catch mistakes |
| Lighting & materials | `openai/gpt-5.6-sol` | physics-heavy node graphs; leads the aggregate index; text-only, it reads the scene as a code-authored report (decided 2026-10-06) |
| Reviewer | `deepseek/deepseek-v4.1-flash` | image input confirmed; different family from the Builder. `deepseek-v4-flash-0731` is text-only and must not be used here |
| Researcher | `openai/gpt-5.6-luna` | long context, tool use, cheap |

The registry holds seven slugs: `openai/gpt-5.6-luna`, `openai/gpt-5.6-sol`, `deepseek/deepseek-v4-pro-0813`, `deepseek/deepseek-v4.1-flash` and `anthropic/claude-haiku-4.5` (probed 2026-10-05), and `deepseek/deepseek-v4-flash` and `~deepseek/deepseek-v4-flash-latest` (probed 2026-10-09, text-only). `~deepseek/deepseek-v4-flash-latest` is an alias that follows the newest V4 Flash model, so the model behind it can change without a new probe. It is the one exception to pinned slugs, chosen by the owner, and is marked as an alias in `/admin`. `deepseek/deepseek-v4-flash-0731`, the predecessor's model, is not listed on the owner's key (2026-10-09). A slot is changed only from `/admin`, and a saved override there wins over `config/models.yaml`. Excluded by decision (blocked by the owner's OpenRouter guardrail, 2026-10-05): `anthropic/claude-sonnet-5.5`, `anthropic/claude-opus-5.5`, `google/gemini-3.5-flash`, `z-ai/glm-5.3-flash`.

**Gateway probe 2026-10-05.** `deepseek/deepseek-v4.1-flash` answered an image correctly through OpenRouter; the other four registry slugs answered text. Startup validation must report a guardrail block as a configuration error naming the slug, not as a model failure.

**Token restrictions (admin, per model).** `/admin` sets for every registry entry: max output tokens per call, context budget per turn, and a daily token ceiling. The budget node counts before the call; exceeding a ceiling refuses the call with a stated reason and the Foreman reports it to the homeowner. Temperature and output caps extend the existing `GenerationProfile`. The model never sees or changes these.
Consumer subscriptions (Claude Pro, SuperGrok) are not backends; Claude Desktop with the Blender MCP addon is the owner's own step-3 workshop, outside the app.

## 5. Tools (plugins)

Each tool is a folder under `backend/plugins/<name>/` with `manifest.yaml` (name, description, kind, role, tools, enabled by default, toggleable) and its implementation. The backend loads every manifest at startup and refuses a malformed one by file name. The homeowner toggles plugins per conversation; the developer enables or disables them globally from `/admin/plugins`. Declarative HTTPS plugins are a second kind: one GET to an allow-listed host, executed with the SSRF guard (global addresses only, pinned IP + SNI, no redirects, cap, timeout, pacing); none ship enabled.

| # | Plugin | Agent | Status | Notes |
|---|---|---|---|---|
| 1 | `blender_build` | Builder | port | `blender_build`; `build_shell` listed, filled in by apartment-intake |
| 2 | `render_turntable` | Builder | port | behind the guard; writes `docs/renders/...` and `viewer.html` |
| 3 | `revise_package` | Designer | port | linked new version from stated changes behind `interrupt()` confirmation |
| 4 | `cut_list` | Designer | port | `derive.py` rule table; zero GPU |
| 5 | `room_fit` | Designer | port | polygon room contract, openings, placement validation |
| — | `intake` | Intake | port | `record_brief`, `record_plan`; not toggleable |
| — | `create_piece` | Designer | port | not toggleable |
| — | `guidelines` | Designer | new | `search_guidelines` over official rules and the owner's notes; hard rules in `config/design_rules.yaml` |
| 6 | `material_cost` | Researcher | port + extend | `price_cut_list`, `manage_remnants`; §5a |
| — | `catalog_research` | Researcher | port | `search_catalog_knowledge`, `check_live_listing`, `compare_products` |
| 7 | `revision_review` | Reviewer | port | render vs spec vs brief; discrepancy list; no write tool |
| 8 | `photoreal_detail` | Lighting | built | detail pass on a copy of `model.blend` over the socket, allow-listed; its render is `final` tier only |
| — | `restyle_render` | Builder | built | draft turntables of a piece's look or a room's style from `config/looks.yaml` and `config/styles.yaml`; in-memory override, nothing saved, appearance only; one guard ticket per variant, never `final`; a piece's variant is rateable |

### 5a. Pricing (kept, reworked)

- Supplier is **toom only**; `RETAIL_SOURCES=toom`. Bauhaus, Kaufland and OKI are excluded, not deferred (robots.txt review 2026-09-15, old README). Web access widens lawful sources, not this list.
- One `supplier_prices` table with provenance `captured` / `override` / `manual` / `snapshot`. Three ways in: a toom product **URL pasted directly** (fetched, added to the corpus and the list in one step, closing the "only corpus products" gap); a **manual entry** created by hand with key, label, category, unit and price; a **manual snapshot** of a page the crawl cannot reach, which may prefill an entry.
- `price_cut_list` keeps sheet packing, remnants-first, cut classification and the immutable snapshot. Unpriced parts mark a pricing incomplete, never guessed.
- The old `/business/price-list` page already creates entries by hand ("Add an entry") and sets overrides; port it as is. Manual snapshots and the price-list page get a browser pass before they count as done.

## 6. Render guard (build first)

Per-render approval, no daily cap. A `final` may run on the render server instead of the laptop (one job per machine); it is quoted from the server's own benchmark and still needs the typed "yes". In RunPod pod mode nothing is created or billed before that "yes", and the quote includes the pod's start-up while no pod is running. Tiers in `config/render.yaml`:

| Tier | Frames | Resolution | Engine | Behaviour |
|---|---|---|---|---|
| draft | 12 | 800×800 | Eevee | runs on the laptop, reports estimate; a piece's draft is a turntable |
| final | 36 | 1500×1500 | Cycles | `interrupt()`, explicit "yes" required; a detail render is a still on the laptop, a turntable only on the render server |

`seconds ≈ frames × megapixels × engine_multiplier × benchmark_seconds_per_megapixel`. The benchmark is a one-off approved first-launch Eevee frame stored under `benchmark`, re-runnable from the dev panel; Cycles multiplier starts at 30 and is calibrated from the first approved final. Show the estimate in human terms before every run. The tool signature **requires** `tier`; raw frame or resolution values are refused. Log tier, estimate and actual to Langfuse. Unit tests: tier parsing, estimate maths, interrupt on final, refusal on bypass.

## 7. Code to port from Interior_Design_App

| Need | Source path |
|---|---|
| Spec contract, validation, layers | `backend/app/blender/{schemas,spec_contract,layers}.py`, templates in `backend/fixtures/packages/templates/` |
| Generators, runner, storage | `backend/app/blender/generators/{build_custom_build,build_room_scene,render_preview}.py`, `runner.py`, `storage.py` |
| Cut list derivation | `backend/app/blender/custom_build/derive.py`, `shop_csv.py` |
| Room contract | `backend/app/blender/room_contract.py`, fixtures `room-scene-*.json` |
| Revision and business tools | `backend/app/agent/tools/`, `business_graph.py`, `stages.py` (stages become agents) |
| Gateway, registry, settings | `backend/app/agent/models/`, `operator_config.py`, `budget.py` |
| Memory, checkpointer | `backend/app/agent/memory/` |
| Pricing | `backend/app/api/price_list.py`, `snapshots.py`, `supplier_prices` domain code |
| toom ingestion, hybrid retrieval, live lookup | `backend/app/ingestion/`, `tools/search_catalog_knowledge.py`, `check_live_listing.py`, `live_fetcher.py` |
| Guard, feedback, plugins, Langfuse | `prompts.py`, `feedback_policy.py`, `agent/plugins/`, `observability/` |
| Auth (single admin account) | `api/gate.py`, auth routes; roles collapse to owner + dev route |
| Apartment shell generator, photo-match procedure | `.claude/skills/blender-Grok-package/blender-apartment-render/scripts/generate_shell.py` and `references/` (skill text becomes tool code and prompts) |
| Studio UI, viewer | `frontend/src/components/studio/`, `renders/`, `reference/viewer.html` |

Separate named objects per part: confirmed in `build_custom_build.py` (one object per cut-list id, `<id>#<n>` for further copies, parented to one empty per module). The "revision bot" of the old brainstorm is `revise_package`; a render-versus-brief reviewer did not exist and is new (§5 #7).
Dropped: public studio site, client area and Styler Bot, quotes, contracts, project board, three-role model, Listening Wall generator unless needed.

## 8. Security guard

- Prompt-injection delimiters on every retrieved chunk, live page, snapshot, plugin result and upload, with the guard composed by code after any editable prompt.
- `bpy` allow-list for step 3: permit `bpy.ops.mesh.*`, `bpy.ops.object.*`, `bpy.data.*`, modifiers, materials, render settings; block `os`, `subprocess`, `shutil`, `open()` outside `docs/renders/` and the package folder, and `bpy.ops.wm.*` except `save_mainfile` to the project `.blend` and `open_mainfile` of the detail pass's own `detail.blend` (a literal path, nothing else). The backend's own scripts go through the same allow-list. The checked-in headless generators are not live scripts: they may call `bpy.ops.import_scene.gltf` and `bpy.ops.wm.obj_import`, and only on a built package's `model.glb` or a model-library file that passed the upload checks (room-composition). A live script may not import a file.
- Single-user password login; the developer route is additionally gated. Session, project and scope come from the cookie and path, never from a model argument; every model-generated argument is Pydantic-validated; no model-run SQL.
- Secrets never enter graph state, prompts, tool output or logs.

## 9. Conventions

Backend in `backend/`: `uv sync`, `uv run alembic upgrade head`, `uv run pytest -m "not slow"`, `uv run ruff check .`. Frontend in `frontend/`: `pnpm install`, `pnpm test`, `pnpm lint`, `pnpm build`. Run lint and tests before every commit. Backend tests share one database: never run two pytest processes at once. Commit style: imperative subject, body explains why.

### 9a. House file

Long-term memory: every room's measured polygon, heights and openings; style preferences; pieces designed and their versions; reviews of a version (open items reach the Designer); render feedback (thumbs and comment with prompt, model, tier); generator-extension requests. A conversation is about at most one piece (a room may hold many pieces). The house file holds everything, but a conversation sees only its slice of it: rooms are confirmed per conversation (never assumed), and the prompt carries that room and the single bound piece in full, so nothing from other conversations reaches it. Foreman, Intake and Designer read that slice first. Owned by the single account.

## 10. Open questions — ask, do not assume

None open as of 2026-10-05.

## 11. Build order

1. [x] Port foundation: FastAPI, Postgres, migrations, registry, gateway, Langfuse, auth (owner + dev route) — `openspec/changes/port-foundation`
2. [x] Render guard, Eevee defaults, first-launch benchmark; port generators and runner behind it — `openspec/changes/render-guard`
3. [x] House file + checkpointer — `openspec/changes/agent-loop`
4. [x] Foreman → Intake → Designer → Builder loop with `revise_package`, `cut_list`, `room_fit` — `openspec/changes/agent-loop`
4a. [x] Intake vision read of blueprints and photos into the house file; headless apartment shell generator — `openspec/changes/apartment-intake`
5. [ ] Pricing port and rework (§5a) + Researcher
6. [x] Reviewer (`revision_review`) with a vision model — `openspec/changes/render-reviewer`
7. [x] Plugin manifests, homeowner toggles, dev panel with per-agent model routing and token restrictions — `openspec/changes/plugins-and-budgets`
8. [x] `photoreal_detail` over the socket, allow-list, `final` tier — `openspec/changes/photoreal-detail`
9. [x] Feedback capture → house file + Langfuse tags — `openspec/changes/feedback-capture`
10. [x] Cloud render offload — asked for 2026-10-06 — `openspec/changes/render-offload`
10a. [x] RunPod pod created after approval and deleted when idle — asked for 2026-10-15 — `openspec/changes/render-pod-lifecycle`
