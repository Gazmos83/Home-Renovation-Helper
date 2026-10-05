## Why

The new repository holds only a build guide, design notes and an empty `uv` project; nothing runs. Every later step in the build order (render guard, house file, agents, pricing) needs a service that starts from validated configuration, migrates its own schema, reaches OpenRouter through one credential, traces to Langfuse and admits exactly one owner. Porting that foundation first, pruned to a single-user product, lets each later change add behaviour instead of scaffolding.

## What Changes

- Add the FastAPI service skeleton: environment-validated settings, unauthenticated health endpoint reporting database reachability, configured-origin CORS with credentials and wildcard rejection, one structured log record per request, secret redaction in every log line.
- Add the PostgreSQL + pgvector schema baseline under Alembic (ordered, reversible migrations), run the LangGraph Postgres checkpointer's own `setup()` at startup and exclude its tables from autogeneration.
- Add the model registry and the per-agent routing file `config/models.yaml`: the five probed registry slugs from CLAUDE.md §4, one slug per agent slot (Foreman, Intake, Designer, Builder, Lighting, Reviewer, Researcher), no backup slot. Unknown slugs, an agent slot left unmapped and a routing entry outside the registry fail startup by name.
- Add the single OpenRouter gateway client with a startup probe of every routed slug: a guardrail block or an unlisted model is reported as a configuration error naming the slug, never as a model failure. The credential never enters graph state, prompts, tool output, logs or responses. Gateway failures surface as a stated inability, not a raw payload.
- Add the Langfuse callback (user, session and project identifiers as trace metadata) that is on only when all three Langfuse values are set and never load-bearing.
- Add single-owner authentication: one owner account bootstrapped from the environment on first start, password hashed with argon2, cookie sign-in and sign-out, a `require_owner` dependency for homeowner routes and a stricter `require_dev` dependency for `/admin` routes that additionally needs the developer gate enabled by configuration. No registration, no roles, no legacy passcode header.
- Carry over the test conventions: deterministic tests for configuration failure, health, CORS, logging, migrations, registry/routing validation, gateway secret exclusion, Langfuse on/off/unreachable and auth; one shared test database; `--live` marker for paid gateway calls.
- Dropped from the port, deliberately: accounts with roles, `POST /auth/register`, `POST /auth/bootstrap` with `X-Admin-Passcode`, `LEGACY_PASSCODE_GATE`, `/admin/users`, anonymous shopper sessions, `RETAIL_SOURCES` wiring (arrives with the pricing port), the operator model picker and prompt editor (arrive with the dev panel), pricing fetch, and every business, client and public router.

**Ladder step and agent:** this change touches no ladder step and binds no agent; it provides the gateway and routing that every agent will use. **Render guard and bpy allow-list:** not affected; no Blender code is ported here.

## Capabilities

### New Capabilities
- `service-foundation`: configuration from the environment with fail-fast validation, health endpoint, CORS, structured request logging, migration-owned schema with the checkpointer excluded, and optional Langfuse tracing.
- `llm-gateway`: one OpenRouter credential, a closed model registry, per-agent routing from a configuration file, startup probe of routed models, secret exclusion and stated failure.
- `owner-auth`: a single owner account bootstrapped from configuration, argon2 password hash, HttpOnly session cookie, sign-in/sign-out/who-am-I, and the two gates (owner, developer) every later route depends on.

### Modified Capabilities
None. `openspec/specs/` is empty in this repository.

## Impact

- New code under `backend/app/`: `config.py`, `main.py`, `db/` (session, models, Alembic env and first migration), `agent/models/` (registry, routing loader, gateway client, probe), `observability/`, `api/auth.py`, `api/gate.py`, `api/health.py`; `config/models.yaml`; `backend/tests/`.
- New dependencies: `pgvector`, `pwdlib[argon2]`, `pyyaml`, `httpx`; dev: `pytest-httpx` or equivalent only if the probe test needs it. Added with `uv add`, lockfile committed.
- New environment variables documented in `.env.example`: `DATABASE_URL`, `TEST_DATABASE_URL`, `OPENROUTER_API_KEY`, `CORS_ORIGINS`, `OWNER_EMAIL`, `OWNER_PASSWORD`, `DEV_PANEL_ENABLED`, `SESSION_COOKIE_SECURE`, optional `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`.
- `docker-compose.yml` for the loopback `pgvector/pgvector:pg17` database with dev and test databases, copied from the predecessor.
- No frontend in this change. The owner signs in with `curl` until the SPA scaffold and `/login` arrive with the homeowner UI change; CLAUDE.md §11 step 1 lists no frontend work.
- Source paths to port are listed in CLAUDE.md §7 (gateway, registry, settings, memory checkpointer, auth, observability).
