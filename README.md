# Home Renovation Agents

Single-user personal project: design custom furniture and room layouts for the
owner's own home, model them in Blender, render cheap turntables, review them
against the brief, and price the build from lawful supplier data. See
[CLAUDE.md](CLAUDE.md) for the "what" and [docs/DESIGN_NOTES.md](docs/DESIGN_NOTES.md)
for the "why".

The service is a FastAPI backend plus a Vite React Studio: one owner, a Foreman
that talks to Intake, Designer and Builder, plugin-folder tools the homeowner
can toggle per conversation, a token budget enforced before every model call,
and a developer panel for routing, generation, plugins and usage.

## Requirements

- Docker (for the loopback PostgreSQL) and `docker compose`
- Python 3.14 and [uv](https://docs.astral.sh/uv/)
- Node.js 22+ and [pnpm](https://pnpm.io/) for the Studio SPA

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

Sign in against the API directly (the Studio SPA signs in the same way):

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

## Chat and the house file

You talk to the **Foreman**; it hands each message to Intake (turns a wish into
confirmed numbers), the Designer (creates and revises pieces, lists parts, checks
a room), the Builder (builds and renders) or the Reviewer (checks a screenshot or
render against the brief and spec), and you never name one. Every model
call needs `OPENROUTER_API_KEY`; the routes below work against a live service
once a key is set. Conversations survive restarts (the Postgres checkpointer).

**In the Studio.** Open **Conversations**, start one, and talk to the Foreman in the
conversation page: the messages, a composer, a **Yes / No** card whenever something
needs your confirmation, and **Add a plan or photo** for blueprints. The **Project**
panel beside it shows the piece, its latest version and build state, how far it has
come (brief, piece, built, rendered, reviewed, detail pass, final) and what to ask
for next. The `curl` calls below are the same API for scripts.

Anything that changes the house — confirmed numbers, a new piece, a revision, a
`final` render — **pauses** until you answer `yes` or `no`:

```bash
# 1. start a conversation (cookie from "Signing in with curl" above)
THREAD=$(curl -s -b cookies.txt -X POST http://localhost:8000/chat/threads \
  -H 'Content-Type: application/json' -d '{"title":"Hall bench"}' | jq -r .thread_id)

# 2. send a turn; the reply says who answered and whether a confirmation is pending
curl -s -b cookies.txt -X POST http://localhost:8000/chat/threads/$THREAD/turns \
  -H 'Content-Type: application/json' \
  -d '{"message":"I want a bench for the hall: 1200 wide, 3000 long, 2400 high, 400 euro, light oak"}'
# → {"reply": "...", "specialist": "intake", "pending": {"confirmation_id": "...", "subject": "brief", "summary": "..."}}

# 3. answer it — "yes" runs the action, "no" (with an optional reason) returns the reason to the agent
curl -s -b cookies.txt -X POST http://localhost:8000/chat/threads/$THREAD/resume \
  -H 'Content-Type: application/json' \
  -d '{"confirmation_id":"<id from the reply>","answer":"yes"}'

# 4. read the conversation (and any pending confirmation), or list them all
curl -s -b cookies.txt http://localhost:8000/chat/threads/$THREAD
curl -s -b cookies.txt http://localhost:8000/chat/threads
```

A new message while a confirmation is pending, or an answer to one that is no
longer pending, is refused with 409. If the conversation memory is unavailable
the turn is refused with 503; a model-gateway failure answers 502 with its class
(`timeout`, `unauthorized`, …) and leaves the unanswered message out of the
thread. Replies never show a model name, a prompt, a token count or a file path;
files are named by their package route, for example
`/packages/hall-bench/versions/1/files/screenshot.png`.

**Reviews.** After a screenshot or a draft turntable exists, ask to check the
piece. The Reviewer returns a discrepancy list (what was expected, what it saw,
which image, how serious) and records it; it cannot change the piece. Ask the
Designer to fix what it found — that is a normal `revise_package` you confirm.
Mark an item resolved or dismissed yourself; closed items leave the Designer's
context:

```bash
curl -s -b cookies.txt http://localhost:8000/packages/hall-bench/versions/1/reviews
curl -s -b cookies.txt -X PATCH http://localhost:8000/reviews/$REVIEW/items/$ITEM \
  -H 'Content-Type: application/json' -d '{"status":"resolved"}'
```

**The house file** is the owner's long-term memory, in the database and the
package folders: every room (polygon, heights, openings), preferences (`style`,
`budget_eur`), pieces with their versions and what changed, reviews of a version,
and **generator-extension requests**. If you ask for something the spec schema cannot express (a
bevelled edge), the Designer says so plainly and the field is recorded as a
request — it never offers Blender code. Rooms and style are written only by a
confirmed brief; pieces and versions only by a confirmed `create_piece` or
`revise_package`. Packages made directly through `/packages` still appear to the
Designer, without a brief.

## Plans, apartments and shells

Intake reads blueprints and room photos (it runs on the image-capable model). Upload
PNG or JPEG images to a conversation (type is read from the file's bytes; at most
`UPLOAD_MAX_BYTES` each, `UPLOAD_MAX_PER_THREAD` per thread; files live under
`UPLOAD_ROOT`, default `docs/uploads`, never in the conversation itself), then attach
them to a turn:

```bash
UPLOAD=$(curl -s -b cookies.txt -X POST http://localhost:8000/chat/threads/$THREAD/uploads \
  -F file=@blueprint.jpeg | jq -r .upload_id)

curl -s -b cookies.txt -X POST http://localhost:8000/chat/threads/$THREAD/turns \
  -H 'Content-Type: application/json' \
  -d "{\"message\":\"This is my flat; the living room is 5.2 m wide.\",\"upload_ids\":[\"$UPLOAD\"]}"
# → a pending "plan" confirmation listing each room's size and area, how the scale was
#   read, the assumptions and any warning; answer it with /resume as for any confirmation
```

A confirmed plan stores an **apartment**: rooms in one plan frame (millimetres), which may
be L- or U-shaped (simple polygons of 3–12 corners). Rooms of one apartment must not
overlap; an edge two rooms share is one wall. Then build and look at its shell:

```bash
curl -s -b cookies.txt http://localhost:8000/apartments                 # list
curl -s -b cookies.txt -X POST http://localhost:8000/apartments/flat/shell   # build (headless, ~10 s)
curl -s -b cookies.txt http://localhost:8000/apartments/flat/shell/versions/1
# screenshot (a Workbench frame, not a render): …/shell/versions/1/files/screenshot.png
curl -s -b cookies.txt -X POST http://localhost:8000/apartments/flat/shell/versions/1/renders \
  -H 'Content-Type: application/json' -d '{"kind":"turntable","tier":"draft"}'
```

Shell renders go through the same render guard as a furniture version: a tier is required,
`frames` and the other raw values are refused by name, the response states the estimate, and
a `final` answers 409 with an `approval_token` until you confirm. In chat the Builder's
`build_shell` and `render_turntable` (with `shell`) do the same. Shells live in
`docs/renders/shells/<apartment>/v<N>/`. Reading a plan with the vision model needs
`OPENROUTER_API_KEY`; everything after a confirmed plan works without a model.

## Pricing, the price list and guidelines

Prices come only from toom, read under this service's stated identity after its robots rules allow the page; a 401, 403, 429 or an unreadable robots file is an answer, reported and never retried another way. Money is euro cents.

```bash
# The toom corpus and the home store (TOOM_HOME_STORE, TODO(user) in .env.example)
uv run python -m app.ingestion toom
uv run python -m app.ingestion --store
# Guideline publications listed in config/guideline_sources.yaml: your own PDFs and .md
# files under docs/guidelines/{pdf,notes}/ (read locally, no request; pdf/ is gitignored)
# or official URLs (robots-gated). A missing file or a refusing host is reported and
# skipped. The official hosts checked on 2026-10-06 refused, so download those yourself.
uv run python -m app.ingestion --guidelines

# The price list (cookie from "Signing in with curl")
curl -b cookies.txt http://localhost:8000/price-list?category=panel
curl -b cookies.txt -X POST http://localhost:8000/price-list -H 'Content-Type: application/json' \
  -d '{"key":"hinge","label":"Hinge","category":"hardware","unit":"per_piece","base_cents":250}'
curl -b cookies.txt -X PUT http://localhost:8000/price-list/hinge/override -H 'Content-Type: application/json' \
  -d '{"cents":300,"note":"bought in bulk"}'
curl -b cookies.txt -X POST http://localhost:8000/price-list/from-url -H 'Content-Type: application/json' \
  -d '{"url":"https://www.toom.de/p/…/3150333","key":"foam-eps","category":"finish"}'
curl -b cookies.txt -X POST http://localhost:8000/price-list/foam-eps/refresh

# Price a version (an immutable record), the remnant rack, guideline notes
curl -b cookies.txt -X POST http://localhost:8000/packages/hall-bench/versions/1/pricings -H 'Content-Type: application/json' -d '{}'
curl -b cookies.txt http://localhost:8000/remnants
curl -b cookies.txt -X POST http://localhost:8000/guideline-notes -H 'Content-Type: application/json' \
  -d '{"title":"Wardrobe passage","body":"Keep it clear.","value":900,"unit":"mm","citation":"Neufert, p. 123"}'
```

Hard design rules live in `backend/config/design_rules.yaml` (each with its quoted source; it ships empty, see the file). The Researcher answers price and product questions in chat; the Designer can search the guideline corpus.

## Photoreal detail (ladder step 3)

For one-off carpentry detail, materials and lighting, the Lighting & materials
specialist works in **your own Blender**: open Blender 5.2.1 with the "MCP for
Blender" addon and start its server (it listens on `localhost:9876`; change
`BLENDER_LIVE_HOST` / `BLENDER_LIVE_PORT`, loopback only). Then, in a conversation
bound to a built piece, ask for realistic oak or soft lighting.

- The first step pauses for your **yes**: the backend copies `model.blend` to
  `<version>/detail/detail.blend` and opens that copy in your Blender, replacing
  the file you had open. `model.blend`, the spec and the cut list are never changed.
- Every script, the agent's and the backend's own, is checked against the `bpy`
  allow-list first. Allowed: `bpy.data`, modifiers, materials and node trees,
  render settings, the mesh/object/material/node/uv/transform operators,
  `save_mainfile()` and `open_mainfile` of this pass's `detail.blend`. Refused,
  naming the construct and line: imports other than `bpy`, `bmesh`, `mathutils`,
  `math`, `random`; `open`, `exec`, `eval`, `getattr` and friends; dunder access;
  text blocks, libraries, handlers, preferences; every render operator.
- Scripts are refused while a headless build or render is running, and a headless
  job waits while a script runs. Every script and its verdict is logged to
  `detail/log.jsonl`.
- The specialist is text-only: after each script it reads the scene as text.
  `detail_screenshot` saves a viewport PNG for **you** at
  `…/files/detail/screens/<n>`; tell it what to change.
- Asking for the final image shows the Cycles estimate and waits for your **yes**;
  it renders `detail.blend` headless through the render guard at tier `final` and
  publishes `detail/still.png` or `detail/frames/` + `detail/viewer.html`. Draft and
  preview are refused for a detail render.

## Render offload (optional)

A `final` Cycles turntable takes about two hours on this laptop. If you rent a GPU box
you can send finals there instead. Nothing is rented or started by the app: you start
and stop the box, and the app only uses it when you have configured it and chosen it.

Set up the box once:

1. Rent a Linux machine with an NVIDIA (OptiX or CUDA) or AMD (HIP) GPU, with `ssh`.
2. Install **Blender 5.2.1** on it (the same version as here; any other is refused).
3. Add your public key to its `~/.ssh/authorized_keys`, and put its host key in a
   known-hosts file here: `ssh-keyscan -t ed25519 <host> > ~/.ssh/hra_known_hosts`
   (check the fingerprint against the provider's).
4. Set in `.env`: `RENDER_OFFLOAD_HOST`, `RENDER_OFFLOAD_USER`, `RENDER_OFFLOAD_KEY_PATH`,
   `RENDER_OFFLOAD_KNOWN_HOSTS_PATH`, `RENDER_OFFLOAD_BLENDER` (absolute path on the
   box) and, if needed, `RENDER_OFFLOAD_PORT` / `RENDER_OFFLOAD_CYCLES_DEVICE`
   (`OPTIX`, `CUDA` or `HIP`). With any of the five main values missing, offload is off.

Then in the developer panel (**Offload**): *Test the connection*, *Run the remote
benchmark* (one Cycles frame, so the estimate is real), and switch **Final renders** to
*On the render server*. Draft and preview always stay on the laptop.

- The estimate for a remote final is the server's own, "on the render server, about N
  minutes", and the typed **yes** is still required.
- If the server is off, unreachable or runs another Blender, the final is **refused
  with the reason before you are asked**; it is never run on the laptop instead. Start
  the box, or switch the target back.
- A job uploads the model and the generator files in one archive, runs the same
  generator with the tier's values, copies the frames back, checks them like any local
  render and removes its folder on the server. One job runs at a time on the server,
  and a laptop draft can run beside it.
- The page lists the last twenty remote jobs with their time and, if you give an hourly
  rate, a euro estimate. That figure, the host and the target are never shown to the
  homeowner. The first remote final recalibrates the server's rate.

## Rating renders

Every published render (still, turntable, in a room, detailed) can be rated with a
thumbs up or down and a comment, so the next design learns from it.

- **Pieces page** (`/pieces` in the Studio): your pieces, their versions, and each
  version's renders with a preview, a viewer link and the thumbs. A rating belongs to
  one render run: render again and the new one starts unrated. Renders made before
  this existed cannot be rated until they are rendered again.
- **In chat**, when you react in words ("the draft is too dark 👎"), the Builder or
  the Lighting specialist proposes the rating and comment and records them only after
  your **yes**.
- Your latest five ratings of a piece are given to the Designer and Lighting, labelled
  as your own words. Each rating is also a Langfuse score on the turn that started the
  render, plus a feedback trace tagged with the rating, tier, agent and model.
- The developer panel's **Feedback** page (`/admin/feedback`) counts ratings per agent,
  model and tier and lists a group's comments. It never changes routing; change a slot
  by hand on the Models page.

```bash
curl -b cookies.txt http://localhost:8000/packages/hall-bench/versions/1/renders
curl -b cookies.txt -X PUT http://localhost:8000/packages/hall-bench/versions/1/renders/turntable/feedback \
  -H 'Content-Type: application/json' -d '{"rating":"down","comment":"too dark"}'
```

## Model routing

Per-agent model routing lives in [`backend/config/models.yaml`](backend/config/models.yaml):
exactly one registry slug per agent slot, no backup. It is validated against the
closed registry at startup — a missing slot, an unknown slug, a `backup`/`fallback`
key, a duplicate slot, or the Reviewer routed to a text-only model stops startup
by name. The developer panel writes per-slot overrides to `operator_settings`
(`routing:<slot>`), which resolve over the file and apply to the next turn
without a restart. A switch is probed first; a failed probe leaves routing
unchanged.

## Plugins

Each tool group is a folder under [`backend/plugins/`](backend/plugins/) with
`manifest.yaml` and `tool.py`. The backend loads every manifest at startup and
stops naming the file on a missing field, an unknown field, a duplicate tool, a
built-in tool with no implementation, or an unknown role. A built-in manifest may name other agents in `also_for` that share its tools (the
rating tool serves the Builder and Lighting). `intake` and
`create_piece` are not toggleable; the rest of the shipped tools are.

**HTTPS plugins** are a second kind: a manifest with an input schema, an output
schema and one GET to a host on `PLUGIN_ALLOWED_HOSTS` (empty by default). The
executor re-checks the host, refuses non-global addresses, connects to the
checked IP with SNI, follows no redirect, caps the body, times out, and wraps
the result as untrusted content. Every call is audited without arguments or
body. No HTTPS plugin ships enabled.

Toggle a plugin for one conversation:

```bash
curl -b cookies.txt http://localhost:8000/chat/threads/$THREAD/tools
curl -b cookies.txt -X PUT http://localhost:8000/chat/threads/$THREAD/tools/room_fit \
  -H 'Content-Type: application/json' -d '{"enabled":false}'
```

A change applies from the next turn. Switching off `create_piece` is 409.

## Token restrictions

Each registry model has a context budget per turn (default 32 000) and a daily
token ceiling (default 2 000 000), plus the generation profile's output cap.
Before every call the request is counted (characters × 1.2, each image 1 100)
and fitted; history is trimmed oldest-first without splitting a tool call from
its result. A request that does not fit, or that would pass the day's ceiling
(Europe/Berlin midnight), is refused in the reply by role ("Designer can't take
this on right now: today's limit is reached; it resets at midnight") with no
model slug or token figure.

## Developer panel

With `DEV_PANEL_ENABLED=true` and a signed-in session:

- `GET /admin/models` — registry, routing per slot, profiles, restrictions, today's usage
- `PUT /admin/routing/{slot}` `{"model":"anthropic/claude-haiku-4.5"}` — probe then switch
- `PUT /admin/models/{slug}/generation` and `/budget` — profile and token restrictions
- `GET/PUT /admin/plugins` — global enablement; `GET /admin/plugins/{name}/invocations`
- `GET /admin/usage?days=1` — per model per day (at most 31)

With the panel off these answer 404.

## Studio SPA

```bash
cd frontend
pnpm install
pnpm dev          # http://localhost:5173, proxies the API routes to the backend
                  # (pages: Price list, Snapshots, Remnants, Guidelines, Conversations)
pnpm test && pnpm lint && pnpm build
```

Sign in, then **Conversations** lists each thread's tools by plain name (no
models or tokens). Tools that cannot be toggled show as always on. When
`DEV_PANEL_ENABLED=true`, **Models**, **Plugins** and **Usage** appear under
`/admin/*`; a 404 from `GET /admin/models` hides the tree.

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
cd ../frontend
pnpm test && pnpm lint && pnpm build
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
and its window, `BLENDER_LIVE_HOST` (`127.0.0.1`, loopback only), `BLENDER_LIVE_PORT` (9876),
`BLENDER_LIVE_TIMEOUT_SECONDS` (120), `PLUGIN_ALLOWED_HOSTS` (empty), plugin timeout / response cap /
pacing, `BUDGET_TIMEZONE` (`Europe/Berlin`), and the three Langfuse values
(tracing is off unless all three are set).
