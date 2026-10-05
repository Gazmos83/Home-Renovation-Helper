## Context

See proposal.md for motivation. The predecessor at `/home/pingu/Applications/Interior_Design_App/backend` already implements each piece for a three-role product: `config.py` (Pydantic settings with CSV parsing, wildcard-origin and unknown-model validators, `safe_summary()` redaction, `ConfigurationError` naming variables), `main.py` (lifespan that runs `PostgresSaver.setup()` non-fatally, JSON request logging middleware, outermost CORS), `api/gate.py` + `api/auth.py` + `auth/{passwords,sessions,accounts}.py` (argon2 via pwdlib, SHA-256 token hashes with sliding expiry, generic refusals, dummy-hash verification), `agent/models/{registry,openrouter_client}.py` (frozen `ModelEntry`, `ChatOpenAI` with `extra_body.provider.require_parameters`, `gateway_errors` mapping to classes), `operator_config.py` (`generation:<model_id>` profiles in `operator_settings`), `observability/{langfuse,usage}.py` (lazy handler, warn-once outages, email masking, `model_usage` rows), `db/alembic/env.py` (checkpointer tables excluded from reflection and autogenerate) and `conftest.py` (migrated shared test database, `--live`).

Constraints from CLAUDE.md: one owner plus a developer route; one model per agent slot, no backup, changed only from `/admin`; the model never sees or alters token restrictions; secrets never in state, prompts, tool output or logs; Python 3.14 with `uv`; one shared test database.

## Goals / Non-Goals

**Goals:**
- A service that boots, migrates, probes its routed models, traces optionally and admits one owner, with the predecessor's test depth.
- Port by copying files and deleting, not by rewriting: keep names, error classes and log event names where the behaviour is unchanged so later ports (memory, tools, pricing) drop in.
- Make per-agent routing a first-class, validated configuration file so step 4 (Foreman and specialists) only has to ask `routing.model_for("designer")`.

**Non-Goals:**
- No agent graph, no chat route, no tools, no house file (steps 3 and 4).
- No developer panel UI or routes that change the model or profile (step 7). The storage shape is prepared; the endpoints are not.
- No frontend. No `RETAIL_SOURCES`, ingestion, embeddings or pgvector-backed tables beyond enabling the extension.
- No token restrictions beyond the generation profile defaults (step 7 adds caps, context budgets and the daily ceiling on top of the ported `budget.py`).

## Decisions

1. **Owner bootstrapped from configuration, not a bootstrap route.** The predecessor created the first admin via `POST /auth/bootstrap` with `X-Admin-Passcode`. A single-user app has no second actor to protect against during bootstrap and no passcode gate to keep alive, so the lifespan creates the owner from `OWNER_EMAIL` and `OWNER_PASSWORD` when the account table is empty and never overwrites an existing hash. *Alternative:* keep the bootstrap route; rejected because it adds a credential (`ADMIN_PASSCODE`) with no remaining purpose and CLAUDE.md §1 forbids a passcode opening any surface.

2. **Developer gate = owner session + `DEV_PANEL_ENABLED`, answering 404 when disabled.** The homeowner view must show no trace of models or costs; 404 rather than 403 keeps the route's existence private. *Alternative:* a second password for `/admin`; rejected as a second credential for the same person. The flag can be flipped per environment (on for the owner's laptop, off for a demo).

3. **Routing file `config/models.yaml`, validated at startup against the registry.** Shape: `agents: {foreman: <slug>, intake: <slug>, …}` with exactly the seven slots; any extra key (including `backup`, `fallback`) is an error. The Reviewer slot additionally requires `supports_images`. Loaded into a frozen `Routing` object on `app.state`; agents read slots by name. *Alternative:* keep `operator_settings.agent_model` as the single selected model; rejected because the product routes per agent and CLAUDE.md §4 says routing lives in a file. Step 7's panel will write per-slot overrides to `operator_settings` (`routing:<slot>`), and the loader already resolves `override ?? file`, so that change adds endpoints only.

4. **Registry rebuilt with the five probed slugs and `supports_images`.** `ModelEntry` gains `supports_images: bool`; the `availability` field stays so a later probe failure can mark a slug unavailable with a reason. Entries: `openai/gpt-5.6-luna`, `openai/gpt-5.6-sol`, `deepseek/deepseek-v4-pro-0813`, `deepseek/deepseek-v4.1-flash` (images), `anthropic/claude-haiku-4.5`, all `validated_on 2026-10-05`. The four guardrail-blocked slugs are listed in a module comment, not as entries, so they cannot be selected. Pricing (`pricing.py`) is not ported now.

5. **Startup probe is a lifespan step with `GATEWAY_PROBE_ENABLED` (default on).** One tiny text completion per distinct routed slug (an image probe for slots that need images), through the same `ChatOpenAI` client and `gateway_errors` mapping, run concurrently. A `forbidden`/`refused` class or an "unlisted model" response becomes `ConfigurationError("routing: <slot> → <slug> blocked by gateway: <reason>")` and startup stops. Tests disable the probe through settings; the `--live` suite runs it for real. *Alternative:* probe lazily on first use; rejected because a blocked Reviewer would surface mid-session, which is exactly the "model failure" misreport §4 forbids.

6. **Keep `operator_settings` and the `generation:<slug>` profile JSON.** The table and `GenerationProfile` port unchanged; `select_model`, prompt keys and pricing checks are not ported. Per-slot overrides and token caps (step 7) will be new keys in the same table.

7. **Usage recording (`model_usage`) ports now, with `owner_user_id` only.** The anonymous `session_id` column and its FK go; `project_id` stays nullable for the house-file step. Recording with tracing on or off is already tested in the predecessor.

8. **Tests keep the predecessor's shape.** Root `conftest.py` with `TEST_DATABASE_URL` default `postgresql://postgres:postgres@127.0.0.1:5432/home_renovation_test`, a session-scoped `migrated_database`, `clean_env`, `settings` fixture with `_env_file=None`, `--live` flag. Role tests become owner/dev gate tests; register and bootstrap tests are dropped.

9. **Dependencies.** `uv add pgvector pwdlib[argon2] pyyaml httpx`; no torch, sentence-transformers, bs4 or pillow until the steps that need them. The `vector` extension is created by the first migration so later steps do not need a separate migration for it.

## Risks / Trade-offs

- [The probe costs a few gateway calls per boot and needs the network] → Flag to disable; tests and offline boots skip it with a stated summary line; the live suite exercises it.
- [A slug listed on 2026-10-05 disappears from OpenRouter later] → The probe reports it as a configuration error naming the slug at the next boot; the fix is a one-line routing edit to another registry entry.
- [Owner password stored in `.env`] → Documented as the initial password only; the first sign-in works and a later password change (step 7) is not overwritten on restart. `.env` is gitignored.
- [Checkpointer setup non-fatal means the service can be "up" without memory] → Health keeps reporting the database; the startup log says so; the chat route (step 4) refuses with a reason, as in the predecessor.
- [Porting `budget.py` early without the panel that configures it] → Defer `budget.py` entirely to step 7 rather than port unused code; the generation profile defaults are enough for step 4 to start.

## Migration Plan

Greenfield: `uv sync`, start the compose database, `uv run alembic upgrade head`, set `.env` from `.env.example`, `uv run uvicorn app.main:app`. Rollback is `alembic downgrade base`. Nothing from the predecessor's database is migrated; the old repo stays untouched.

## Open Questions

None that change the specs or tasks. The session cookie name (`hr_session`) and the dev-panel flag name are recorded as assumptions in tasks and `.env.example`; renaming either later is a one-line change.
