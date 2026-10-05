# Home Renovation Agents

Single-user personal project: design custom furniture and room layouts for the
owner's own home, model them in Blender, render cheap turntables, review them
against the brief, and price the build from lawful supplier data. See
[CLAUDE.md](CLAUDE.md) for the "what" and [docs/DESIGN_NOTES.md](docs/DESIGN_NOTES.md)
for the "why".

This change (`port-foundation`) ships the backend foundation: a FastAPI service
that starts from validated configuration, owns its PostgreSQL + pgvector schema
through Alembic, runs the LangGraph checkpointer, reaches every model through one
OpenRouter credential with a startup probe, traces optionally to Langfuse, and
admits exactly one owner. No frontend, agents, Blender tools or pricing yet —
those arrive with later changes (see CLAUDE.md §11).

## Requirements

- Docker (for the loopback PostgreSQL) and `docker compose`
- Python 3.14 and [uv](https://docs.astral.sh/uv/)

## Setup

```bash
# 1. Start the database (dev + test databases, loopback only)
docker compose up -d

# 2. Configure the backend
cp .env.example .env            # then edit OPENROUTER_API_KEY, OWNER_EMAIL, OWNER_PASSWORD
cd backend
uv sync                         # installs dependencies from uv.lock

# 3. Create the schema
uv run alembic upgrade head
```

`OWNER_PASSWORD` is the **initial** owner password (at least ten characters). The
owner account is created on first start from `OWNER_EMAIL`/`OWNER_PASSWORD`; a
password changed later survives restarts because the stored hash is never
overwritten.

## Run

```bash
cd backend
uv run uvicorn app.main:create_app --factory --reload
```

- `GET /health` → `{"service":"ok","database":"reachable"}` (200), or 503 when the
  database is unreachable. Unauthenticated.
- The startup gateway probe sends one minimal call per routed model. Set
  `GATEWAY_PROBE_ENABLED=false` for an offline boot.

### Signing in with `curl`

There is no frontend in this change. Sign in against the API directly:

```bash
# Sign in — stores the session cookie in cookies.txt
curl -c cookies.txt -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"owner@example.com","password":"your-owner-password"}'

# Who am I — uses the cookie
curl -b cookies.txt http://localhost:8000/auth/me

# Sign out
curl -b cookies.txt -X POST http://localhost:8000/auth/logout
```

The session cookie is `hr_session` (HttpOnly, SameSite=Lax; `Secure` when
`SESSION_COOKIE_SECURE=true`). Sign-in attempts are rate-limited per address and
network (`AUTH_RATE_LIMIT`).

## Renders and packages

Every Blender render passes the **render guard** (CLAUDE.md §6). Tiers live in
[`backend/config/render.yaml`](backend/config/render.yaml): `draft` 12 frames at
600², `preview` 24 at 1000² (both Eevee), `final` 36 at 1500² (Cycles). A request
names a tier and nothing else — `frames`, `resolution`, `width`, `height`,
`samples` and `engine` are refused by name. Before every run the response gives
the estimate in plain terms; a `final` answers 409 with the estimate and a token
until you confirm with `yes`.

**Run the benchmark first** — no render is allowed until one exists, so the
estimate is real. It builds the reference desk once and times one 1000² Eevee
frame (about 10 s):

```bash
# DEV_PANEL_ENABLED=true in .env, then sign in (see above), then:
curl -b cookies.txt -X POST http://localhost:8000/admin/render/benchmark
# or without the service:  uv run python -m app.render.benchmark
```

Then create a package, render a draft turntable, and look at it:

```bash
# 1. a package from a spec (the shipped fold-down desk); builds in the background
curl -b cookies.txt -X POST http://localhost:8000/packages \
  -H 'Content-Type: application/json' \
  -d "{\"package_id\":\"hall-bench\",\"spec\":$(cat backend/fixtures/packages/templates/fold-down-desk.json)}"

# 2. its status and files
curl -b cookies.txt http://localhost:8000/packages/hall-bench/versions/1

# 3. a draft turntable (the response states the estimate)
curl -b cookies.txt -X POST http://localhost:8000/packages/hall-bench/versions/1/renders \
  -H 'Content-Type: application/json' -d '{"kind":"turntable","tier":"draft"}'

# 4. open docs/renders/hall-bench/v1/viewer.html in a browser and drag to turn it
```

A `final`: `POST …/renders` with `"tier":"final"` → 409 with `estimate` and
`approval_token`; then `POST …/renders/approve` with
`{"approval_token":"…","confirm":"yes"}`. Edit a spec into a new version with
`PUT /packages/<id>/spec`. Files are served by exact name from
`/packages/<id>/versions/<n>/files/<name>` (`model.glb`, `spec.json`,
`cutlist.csv`, `hardware.csv`, `screenshot.png`, `still.png`, `viewer.html`,
`scene.json`, `frames/<n>`, `room/…`). A room render adds a `room` document
(`output: {"kind": …}` only) to the render request.

Builds and renders are written to `docs/renders/<package-id>/v<N>/` (contents
gitignored; override with `RENDER_ROOT`). A build also writes `screenshot.png`, a
fast Workbench frame for progress checks; it is not a render and needs no tier.
Blender is `BLENDER_BIN` (default: the pinned 5.2.1 LTS); without it the service
still boots, and only builds and renders answer 503.

## Model routing

Per-agent model routing lives in [`backend/config/models.yaml`](backend/config/models.yaml):
exactly one registry slug per agent slot, no backup. It is validated against the
closed registry at startup — a missing slot, an unknown slug, a `backup`/`fallback`
key, a duplicate slot, or the Reviewer routed to a text-only model stops startup
by name. The developer panel (a later change) writes per-slot overrides to
`operator_settings` (`routing:<slot>`), which resolve over the file.

## Migrations

```bash
cd backend
uv run alembic upgrade head        # apply
uv run alembic downgrade base      # revert (leaves the owner's data gone, schema empty)
```

The LangGraph checkpointer owns its own tables and creates them at startup; they
are excluded from Alembic autogenerate.

## Tests

```bash
cd backend
# Point the suite at the test database (or set TEST_DATABASE_URL).
export TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/home_renovation_test
uv run ruff check .
uv run pytest -m "not slow"
```

The suite shares one test database — never run two `pytest` processes at once.
Tests that spend real money on the OpenRouter gateway are marked `live` and
skipped unless `--live` is passed:

```bash
uv run pytest --live -m live       # paid; runs the real probe once
uv run pytest --blender -m blender # runs the pinned Blender (draft tier + one benchmark frame)
```

## Environment variables

Every variable is documented in [`.env.example`](.env.example). Required:
`DATABASE_URL`, `OPENROUTER_API_KEY`, `CORS_ORIGINS`, `OWNER_EMAIL`,
`OWNER_PASSWORD`. Optional with defaults: `TEST_DATABASE_URL`,
`DEV_PANEL_ENABLED` (false), `GATEWAY_PROBE_ENABLED` (true),
`SESSION_COOKIE_SECURE` (false), `AUTH_SESSION_DAYS` (14), `AUTH_RATE_LIMIT` (10)
and its window, and the three Langfuse values (tracing is off unless all three
are set).
