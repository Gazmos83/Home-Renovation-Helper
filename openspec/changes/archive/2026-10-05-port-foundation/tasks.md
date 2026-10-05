## 1. Project skeleton and dependencies

- [x] 1.1 Add runtime deps `pgvector`, `pwdlib[argon2]`, `pyyaml`, `httpx` with `uv add`; verify `uv sync` succeeds and `backend/uv.lock` is updated
- [x] 1.2 Copy `docker-compose.yml` (pgvector pg17 on loopback with `home_renovation` and `home_renovation_test` databases) and write `.env.example` with every variable from proposal.md Impact; verify `docker compose up -d` starts and both databases accept a connection
- [x] 1.3 Create `backend/app/{__init__,config,main,logging}.py`, `app/api/`, `app/db/`, `app/agent/models/`, `app/observability/`, `app/auth/` packages and `backend/conftest.py` with `clean_env`, `settings`, `migrated_database` fixtures and the `--live` flag; verify `uv run pytest --collect-only` runs with zero errors

## 2. Configuration and logging

- [x] 2.1 Port `config.py` pruned to: `DATABASE_URL`, `TEST_DATABASE_URL`, `OPENROUTER_API_KEY`, `CORS_ORIGINS`, `OWNER_EMAIL`, `OWNER_PASSWORD` (min 10 chars), `DEV_PANEL_ENABLED` (default false), `GATEWAY_PROBE_ENABLED` (default true), `SESSION_COOKIE_SECURE`, `AUTH_SESSION_DAYS`, `AUTH_RATE_LIMIT`/window, Langfuse host and keys, `LANGFUSE_TRACING_ENVIRONMENT`; keep `ConfigurationError` naming upper-cased variables and `safe_summary()` redaction; verify `tests/test_config.py` covers missing URL, missing key, empty and wildcard origins, weak owner password, several errors at once and redaction of key, password, Langfuse keys and DSN password
- [x] 2.2 Port `logging.py` (JSON formatter, `log_requests` middleware, `handle_unexpected_error` returning a generic 500); verify `tests/test_logging.py` asserts one record per request with method, path, status, duration and that a raised error logs path and error type while the body carries no detail

## 3. Database, migrations, checkpointer

- [x] 3.1 Port `db/session.py` (`to_sqlalchemy_url`, `make_engine` with `pool_pre_ping`, `database_reachable`) and `db/models.py` with tables `users` (no role column), `auth_sessions`, `operator_settings`, `model_usage` (owner FK, nullable `project_id`, `trace_id`); verify unit tests import the metadata and `ruff check` passes
- [x] 3.2 Port `db/alembic/` (`env.py` with `CHECKPOINTER_TABLES` excluded, URL from `ALEMBIC_DATABASE_URL` → `DATABASE_URL` → settings, `compare_type=True`, NullPool) and `alembic.ini`; write migration 0001 creating `CREATE EXTENSION IF NOT EXISTS vector` plus the four tables with downgrade; verify `alembic upgrade head` then `downgrade base` on the test database leaves no application table
- [x] 3.3 Port `tests/test_alembic_excludes_checkpointer.py`; verify autogenerate against a database holding checkpointer tables proposes no operation on them
- [x] 3.4 Port `agent/memory/short_term.py` pool and `make_checkpointer`, and the lifespan step that runs `setup()` non-fatally; verify `tests/test_startup_checkpointer.py` finds the four checkpointer tables after the lifespan and that an unreachable DSN leaves `app.state.checkpointer` as `None` with a warning logged

## 4. Health and CORS

- [x] 4.1 Add `GET /health` returning 200/503 with `{"service":"ok","database":"reachable|unreachable"}`; verify `tests/test_health.py` covers both outcomes using a port-1 DSN for the unreachable case
- [x] 4.2 Add outermost `CORSMiddleware` from configured origins with credentials; verify `tests/test_cors.py` admits a listed origin with credentials, denies an unlisted one, and startup fails on `*`

## 5. Model registry, routing and gateway

- [x] 5.1 Rewrite `agent/models/registry.py` with `ModelEntry` gaining `supports_images`, the five slugs from design.md decision 4 dated 2026-10-05, and the blocked slugs recorded in a comment; verify `tests/test_model_registry.py` asserts the closed set, image support on `deepseek/deepseek-v4.1-flash` only, and `is_known` refusing unknown slugs
- [x] 5.2 Write `config/models.yaml` with the seven slots from CLAUDE.md §4 and `agent/models/routing.py` that loads it, resolves `operator_settings` `routing:<slot>` overrides over the file, and fails by name on a missing slot, unknown slug, extra/fallback key, duplicate slot, or a Reviewer slug without image support; verify `tests/test_routing.py` covers each failure and the happy path, and the startup summary lists slot → slug
- [x] 5.3 Port `agent/models/openrouter_client.py` (`build_chat_model`, `PROVIDER_ROUTING`, `GatewayError` classes, `gateway_errors`) unchanged except imports; verify `tests/test_openrouter_client.py` asserts `extra_body.provider.require_parameters` on the wire, that an ambient `OPENAI_API_KEY` is ignored, that the configured key never appears in a logged or returned error, and the error class mapping for timeout, rate limit, unauthorized, forbidden
- [x] 5.4 Port `GenerationProfile`, `profile_for`, `model_kwargs` and the `operator_settings` read/write helpers from `operator_config.py` into `agent/models/profiles.py`, without `select_model`, prompt keys or pricing; verify `tests/test_profiles.py` shows the default profile sends no temperature or cap, temperature is dropped for a model without support, and a stored profile survives a fresh instance
- [x] 5.5 Add `agent/models/probe.py`: one minimal call per distinct routed slug (image probe for image slots), concurrent, mapped through `gateway_errors`; a refused/forbidden/unlisted result raises `ConfigurationError` naming slot, slug and reason; wire it into the lifespan behind `GATEWAY_PROBE_ENABLED`; verify `tests/test_probe.py` with a fake transport covers all-answer, guardrail block naming the slug, and the disabled path logging "probe skipped"
- [x] 5.6 Port `tests/test_openrouter_live.py` as a `live` test that runs the real probe for every routed slug; verify it is skipped without `--live` and passes with it (paid call, run once)

## 6. Observability

- [x] 6.1 Port `observability/langfuse.py` (`Tracing`, `turn()` with owner/session/project metadata, warn-once, `mask_personal_data`, `flush`) and construct it in the lifespan; verify `tests/test_langfuse_tracing.py` covers off-unless-configured, metadata ids present, broken handler and unreachable exporter never failing the turn and logging once without keys, and email masking
- [x] 6.2 Port `observability/usage.py` (`UsageRecorder`, `operation`, `attach`) with owner-only ownership; verify `tests/test_usage_recorder.py` covers both token-shape fallbacks, `None` not 0, and a swallowed DB failure
- [x] 6.3 Add the startup summary log line reporting tracing on/off, probe run/skipped and routing; verify a test asserts the summary contains no secret and names tracing state

## 7. Owner authentication and gates

- [x] 7.1 Port `auth/passwords.py` (argon2, min length 10, `DUMMY_HASH` verification) and `auth/sessions.py` (token_urlsafe, SHA-256 hash, sliding expiry, revoke); verify `tests/test_passwords.py` and `tests/test_auth_sessions.py` pass unchanged apart from imports
- [x] 7.2 Replace `auth/accounts.py` with owner-only helpers (`ensure_owner(session, email, password)`, `find_by_email`, `get_owner`) and add the lifespan step that creates the owner when the table is empty and never overwrites an existing hash; verify `tests/test_owner_bootstrap.py` covers first start, later start with a changed hash, and weak configured password failing startup
- [x] 7.3 Port `api/session.py` cookie helpers with cookie name `hr_session` (HttpOnly, SameSite=Lax, secure from settings) and drop the anonymous session cookie; port `api/auth.py` with only `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` and the auth rate limit; verify `tests/test_auth_api.py` covers sign-in sets the cookie and stores a hash, generic 401 for wrong password and unknown email, idempotent logout, `me` returning id and email only, expired session refused, 429 after repeated failures, and no password in any log record
- [x] 7.4 Rewrite `api/gate.py` as `require_owner` (cookie only, fixed 401 message) and `require_dev` (owner session plus `DEV_PANEL_ENABLED`, 404 when disabled); verify `tests/test_gates.py` on a miniature app covers valid cookie, no cookie, owner id in body ignored, dev route with panel on, 404 with panel off, 401 when not signed in

## 8. Assembly and documentation

- [x] 8.1 Assemble `create_app` and the lifespan in order: logging → engine → checkpointer setup → owner bootstrap → routing → probe → tracing → routers (`auth`, health) → CORS outermost; verify `tests/test_app_startup.py` boots the app against the test database with the probe disabled and `/health` answers 200
- [x] 8.2 Write `README.md` (setup, `.env`, compose, migrations, run, tests, `--live`, how to sign in with `curl`) and tick CLAUDE.md §11 step 1 with a pointer to this change; verify the documented commands run from a clean checkout
- [x] 8.3 Run `uv run ruff check .` and `uv run pytest -m "not slow"` against the shared test database with no other pytest running; verify both pass and record the counts in this file's commit message
