## Context

See proposal.md for motivation. The predecessor at `/home/pingu/Applications/Interior_Design_App/backend/app/blender/` holds the pieces: a dependency-free spec contract (`spec_contract.py`, `room_contract.py`) shared with Blender's own Python, Pydantic schemas with `extra="forbid"` that name unknown fields (`schemas.py`), the rule-table derivation (`custom_build/derive.py`) and CSV writers the generator reuses so the emitted shop data equals the derived data row for row, a `LayerRegistry`, the `build_custom_build` and `build_room_scene` generators, a relative-path `storage.py` with staging/sweep conventions, and a `runner.py` whose `Launch` seam lets the ordinary suite run without Blender. Two things make a straight copy impossible: the generators borrow their shared `bpy` helpers from the dropped Listening Wall generator, and the runner, routes and status machine are built on `furniture_packages`/`render_jobs`/`renders` rows that this change deliberately does not add. The custom-build validator also imports `material_key` from the predecessor's pricing module (step 5).

Constraints from CLAUDE.md: the guard is enforced in code including tests (§1, §6); the spec JSON is the source of truth and nothing writes a dimension back; Eevee by default, Cycles only for `final` after a typed approval; viewport screenshots, not renders, for progress; render output under `docs/renders/<package-id>/<version>/`; one headless process at a time; Blender 5.2.1 pinned, engine identifier read from RNA; homeowner routes owner-gated, developer routes dev-gated.

Decisions taken with the owner before this design (2026-10-05): HTTP routes now and the Studio SPA as the next change; filesystem-only package records; the room-scene `output` block loses `frames` and `resolution`.

## Goals / Non-Goals

**Goals:**
- A guard that cannot be bypassed from Python: a render process starts only with a `RenderTicket` the guard minted, and the launcher's refusal is tested.
- The owner's loop end to end without an agent: submit a spec, watch the build, open the turntable, edit the spec, repeat — all through routes the Studio will reuse unchanged.
- Port by extraction, not rewrite: contract, schemas, derive, layers, generators and storage keep their names and error messages so the cut-list, room-fit and Builder changes drop in.
- The emitted `spec.json` keeps the exact shape the predecessor's Studio reads (`overall`, `modules`, `layers`, `parts`, `hardware`, `assembly`, module/part names).

**Non-Goals:**
- No agent, graph or plugin manifest; the Builder (step 4) wraps `guard.authorise` and `runner.*` later.
- No house-file records, no database table, no migration.
- No live socket, no bpy allow-list, no camera matching, no apartment shell (step 4a).
- No cut-list or room-fit *tools*; their library code is ported only because the generators import it.
- No SPA; `viewer.html` beside the frames is the only page this change ships.
- No cloud offload.

## Decisions

1. **Guard = pure function + graph wrapper, authorising with a single-use ticket.** `app/render/guard.py` exposes `authorise(request: RenderRequest, *, tiers, benchmark, approval) -> RenderTicket` that validates the tier, refuses raw knobs by field name, computes the estimate, and for `final` requires `approval == "yes"`. `RenderTicket` is a frozen dataclass with a private constructor token and a `consumed` flag; `runner.run_render` takes a ticket and refuses (raising `RenderNotAuthorised`) when it is absent, foreign or already used. The graph node for step 4 is a thin wrapper: for `final` it calls `interrupt({"estimate": …})` and passes the resumed value as `approval`. *Alternative:* a decorator on the generator CLI; rejected because the CLI runs inside Blender's Python, where nothing can check a ticket, so the gate has to sit where the process is launched.

2. **HTTP approval is a two-step token.** `POST …/renders` with `final` answers 409 `{"failure_class": "approval_required", "estimate": …, "approval_token": …}`; `POST …/renders/approve` with the token and `confirm: "yes"` authorises and starts. Tokens live in memory on `app.state` keyed by package/version with a 15-minute expiry and are single-use. *Alternative:* a `confirm: true` flag on the first call; rejected because the estimate must be seen before the answer is given (§6 "show the estimate in human terms before every run").

3. **Benchmark stored in `operator_settings`, frame under the render root.** `render:benchmark` holds `{"seconds_per_megapixel", "measured_at", "blender_version"}` and `render:cycles_multiplier` holds the calibrated number (absent means 30). The reference scene is the shipped fold-down-desk template built into `<render root>/benchmark/` once and rendered at 1000 × 1000 on Eevee; the frame is kept for inspection. The benchmark is a dev-gated route (`POST /admin/render/benchmark`, `require_dev`) and a CLI (`python -m app.render.benchmark`), never a lifespan step. The guard refuses every render until the key exists, so an estimate is never a guess. *Alternative:* a built-in default seconds-per-megapixel; rejected because a wrong default silently misstates every estimate on the one machine this runs on.

4. **Filesystem records: `<root>/<package-id>/v<N>/` with `status.json`.** `storage.py` is reduced to: `package_dir(root, package_id)`, `version_dir(root, package_id, n)`, `next_version(root, package_id)`, `resolve` (containment check kept verbatim), `staging_dir`/`publish_directory`/`sweep_stale_siblings` (kept verbatim), and `list_packages`. `status.json` is `{"status", "kind", "started_at", "finished_at", "error", "tier", "estimate_seconds", "actual_seconds"}` written atomically (write-then-rename). The lifespan sweeps every `queued`/`running` status to `failed: service restarted`, replacing the predecessor's orphaned-job SQL. Package ids are validated by `^[a-z0-9][a-z0-9-]{0,63}$` and only ever joined under `resolve`. *Alternative:* a SQLite/JSON index file; rejected as a second source of truth to keep consistent with the folders.

5. **Builds do not render; screenshots are Workbench.** `build_custom_build.py` drops the `render.png` step and instead writes `screenshot.png` with `BLENDER_WORKBENCH` at 800 × 500 from `CAM_Iso`. Rationale: §1 "viewport screenshots, not renders, for progress checks" and the Builder flow "blockout → screenshot → OK → guard (draft)". A Workbench frame takes well under a second on this CPU and shows shape, proportion and layers, which is all a progress check needs. The guard's definition of "render" is an Eevee or Cycles frame; the spec says so explicitly so the exemption is reviewable, and the `--blender` test asserts the build publishes no Eevee image. Confirmed by the owner (2026-10-05): screenshots skip the render tiers.

6. **Piece turntable is a new, small generator.** `generators/render_turntable.py` opens the version's `model.blend`, hides the studio floor and dimension helpers as `render_preview` did, places N cameras on a circle around the build's centre at the iso camera's elevation and distance, and renders at the tier's resolution. `generators/render_still.py` is `render_preview` with the tier's resolution. Both read `--tier-frames`, `--tier-resolution` and `--tier-engine` on their argv — values the runner fills from the ticket, never from a caller — and resolve the engine identifier from `bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items` at run time. *Alternative:* reuse `build_room_scene`'s orbit with an empty room; rejected because the owner's default loop is the piece alone and a fake room would show walls.

7. **Room-scene output is tier-driven.** `room_contract._normalise_output` accepts `{kind}` only; `frames` and `resolution` become unknown fields (refused by name, same message path as any other). `RESOLUTIONS` and `DEFAULT_FRAMES` are deleted; `build_room_scene` takes the same three `--tier-*` arguments. `scene.json` gains `tier`, `frames`, `resolution`, `engine`. The two room fixtures and the room-spec tests are updated; the tests that asserted `frames` defaults and bounds are replaced by tests that assert refusal.

8. **Shared `bpy` helpers extracted; Listening Wall dropped.** `_reset_scene`, `_collection`, `_link`, `_add_camera`, `_aim_at`, `_export_glb`, `_verify_package`, `_parse_glb`/`_parse_png` and `GeneratorError` move from `build_listening_wall.py` to `generators/_scene.py` (standard library + `bpy` only, importable inside Blender). `_verify_package` checks the new six-file set. `LayerRegistry` defaults to the custom-build layers since no other kind remains.

9. **`material_key` replaced by a minimal parser.** `app/blender/materials.py` exposes `panel_thickness_mm(material: str) -> int | None`, the one fact `CustomBuildSpec._validate_relationships` needs; the pricing change (step 5) ports the full key normaliser and may replace this helper.

10. **Routes.** Owner-gated router `app/api/packages.py`: `POST /packages` `{package_id, spec}` → 202 `{package_id, version: 1}`; `GET /packages`; `GET /packages/{id}`; `GET /packages/{id}/versions/{n}`; `PUT /packages/{id}/spec` `{spec}` → 202 with the new version; `GET /packages/{id}/versions/{n}/files/{name}` and `…/files/frames/{index}` (closed enumeration, `FileResponse`, media type per name); room files under `…/files/room/{name}`. Owner-gated router `app/api/renders.py`: `POST /packages/{id}/versions/{n}/renders` `{kind: still|turntable, tier, room?}` and `…/renders/approve`. Dev-gated: `POST /admin/render/benchmark`, `GET /admin/render/benchmark`. No rate limit on starts: one owner, and the semaphore serialises. Background work uses FastAPI `BackgroundTasks` with the runner's own sessions, as the predecessor did.

11. **Launch seam and Blender availability.** `app.state.blender_launch` (None in production → `runner.subprocess_launch`) and `app.state.blender_semaphore = asyncio.Semaphore(1)` are created in `create_app`, not the lifespan, because `TestClient` does not always run the lifespan. `Settings.generation_enabled` (binary exists and is executable) is a runtime check: routes that would start Blender answer 503 `{"failure_class": "blender_unavailable", "reason": …}`; listing and files keep working. `BLENDER_BIN` defaults to the pinned path so the owner's `.env` needs nothing new.

12. **Tracing hook.** `Tracing.record_render(**fields)` creates a Langfuse event when enabled and is a no-op otherwise, following `record_output`'s never-raise pattern. The structured records (`render.started`, `render.finished`) are emitted regardless.

13. **Tests.** Unit: tier parsing (missing/duplicate/unknown key/unknown engine), estimate maths (draft, final with multiplier, human wording), interrupt on final (tiny `StateGraph` + `InMemorySaver`, assert `__interrupt__` then resume with `yes`), refusal on bypass (raw knobs; launcher without/with a used ticket). Runner: fake launchers (success writing the files, non-zero exit, hang past timeout, missing binary, two jobs never overlapping). Contract/spec tests ported with the output-shape changes. Routes: against the test database with a fake launcher that writes a minimal package. `--blender` (pinned 5.2.1): build the template, assert the six files and no Eevee image, render a `draft` still and a `draft` turntable and verify counts and sizes, render a `draft` room turntable with the rectangle fixture, and run the benchmark once.

## Risks / Trade-offs

- [Workbench headless rendering needs a GL context like Eevee does] → The predecessor rendered Eevee headless on this laptop, so the same Mesa path serves Workbench; the `--blender` build test proves it on first run.
- [The estimate is linear in frames and megapixels; real cost is not] → Actual is logged beside the estimate on every run; the Cycles multiplier is calibrated from the first final; the formula is the one §6 prescribes and can be refined later without a spec change.
- [A `final` on this CPU can take hours and holds the semaphore] → `BLENDER_TIMEOUT_SECONDS` bounds it (default raised to 4 hours for finals via a per-tier timeout multiplier in `render.yaml`); the approval step shows the estimate first.
- [Filesystem status can be stale after a crash] → Startup sweep marks `queued`/`running` as failed; staging folders are swept before each run.
- [In-memory approval tokens vanish on restart] → Acceptable: the owner re-requests and sees the estimate again; nothing was started.
- [Dropping `output.frames`/`resolution` breaks any room document copied from the predecessor] → Refused by field name with the tier explanation; the two shipped fixtures are updated.
- [Package ids chosen by the owner collide with `benchmark`] → `benchmark` is reserved and refused as a package id.

## Migration Plan

Greenfield on this repository: `uv sync`, `uv run alembic upgrade head` (no new migration), set `BLENDER_BIN` only if the binary is not at the pinned path, start the service, sign in, run `POST /admin/render/benchmark` once (or the CLI), then create a package. Rollback is removing the routes; nothing in the database changes except the two `operator_settings` keys, which are harmless if left.

## Open Questions

None that change the specs or tasks. The per-tier timeout multiplier values and the 15-minute approval-token expiry are recorded as assumptions in `render.yaml` and the routes' docstrings; both are one-line changes.
