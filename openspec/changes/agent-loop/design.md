## Context

See proposal.md for motivation. What exists: the foundation (routing per slot, generation profiles, `Tracing`, `UsageRecorder`, the Postgres checkpointer on `app.state.checkpointer`, owner gate) and `render-guard` (`CustomBuildSpec`/`RoomSceneSpec` with `describe_validation_error`, `derive`, `room_contract.normalise_room_scene`, `storage` version folders with `status.json`, `runner.run_build`/`run_render`, `guard.authorise`/`quote`, `guard_node` with `interrupt()`, `benchmark_store`). The predecessor at `/home/pingu/Applications/Interior_Design_App/backend/app/agent/` holds the pattern to port: a bounded tool-calling `StateGraph` whose `tools` node interrupts before a gated tool runs, `answer`/`resume`/`pending_interrupt` helpers, instruction files with a YAML header, `prompts.py` (guard, `compose_agent_prompt`, `neutralise`), `domain.packages.revise_spec` and `tests/fakes.FakeChatModel`.

Constraints: the homeowner talks only to the Foreman and sees no internals (§1, §3); one model per slot from the file; the spec JSON is the source of truth and nothing writes a dimension back; every render through the guard; secrets never in state; ownership from the cookie, never a model argument (§8). No token budget until step 7.

## Goals / Non-Goals

**Goals:**
- The loop end to end over HTTP with a fake model in tests and the real gateway in use: wish → confirmed numbers → piece v1 built → draft turntable → "three shelves" → v2 → turntable, each gated step a `yes`.
- A graph shape the later agents (Reviewer, Researcher, Lighting) and step 7's toggles and budget drop into: one supervisor, specialists as sub-graphs, tools declared in instruction headers.
- The house file as plain tables written only by confirmed actions, so step 4a (vision intake) and step 9 (feedback) add writers, not shape.

**Non-Goals:**
- No frontend, no streaming; a turn is one request/response.
- No Reviewer, Researcher, Lighting; no plugins or toggles; no `budget.py`; no feedback table (step 9 adds it).
- No vision, no blueprints, no apartment shell (step 4a).
- No live socket.

## Decisions

1. **One compiled graph: Foreman node → specialist sub-graph → end.** `foreman.py` builds `StateGraph(ChatState)` with nodes `load_house` (context from the house file and thread), `foreman` (structured decision `{specialist, reason}` from the `foreman` slot's model, then overridden by code rules: no built piece → never `builder`; nothing confirmed → `intake`), and three sub-graphs `intake`, `designer`, `builder`, each the predecessor's `agent ⇄ tools` loop with `MAX_TOOL_ROUNDS = 6` and the round-cap note. State: `messages` (add_messages), `specialist`, `house_note`, `round_count`, `thread_id`, `package_id`. *Alternative:* three separate compiled graphs chosen by the route; rejected because a pending confirmation must resume inside the specialist that raised it, which one graph with one checkpointer thread gives for free.

2. **Gated tools interrupt before running, in the `tools` node.** Exactly the predecessor's shape: the first gated call in a round is previewed by code (validated and summarised); a valid one `interrupt(summary)`s, and the resumed value `{"answer": "yes"|"no", "reason"?}` decides whether the tool runs or a decline `ToolMessage` carrying the reason goes back to the model. An invalid call skips the pause and returns its refusal. Gated tools: `record_brief`, `create_piece`, `revise_package`, and `render_turntable` only when the tier is `final` (the guard's own `interrupt` is reused: `guard_node`'s `quote` → `interrupt` → `authorise(approval=...)`). Interrupt payloads carry `subject` ∈ {`brief`, `create_piece`, `revise`, `final_render`} so the route can label them.

3. **Specialist models from routing and profiles, built once.** `main.py` builds `app.state.models: dict[slot, ChatOpenAI]` from `routing.model_for(slot)` and `profiles.profile_for(slug).model_kwargs(slug)` through `build_chat_model`; the graph takes a `model_provider(slot)` so tests pass a `FakeChatModel` per slot. Usage rows name the slot's slug via a per-turn `UsageRecorder` per slot (the recorder is attached once per specialist call with the right `model_id`).

4. **House file tables (migration 0002).** `rooms` (id uuid, name unique, corners_mm JSONB, height_mm, wall_thickness_mm, openings JSONB, notes, created/updated), `preferences` (key PK, value text, updated_at), `pieces` (package_id PK validated slug, name, room_id FK SET NULL, brief JSONB, created_at), `piece_versions` (package_id FK, version, revised_from int nullable, changes JSONB, created_at; PK (package_id, version)), `generator_extension_requests` (id, package_id nullable, field, request text, created_at, status `open`), `threads` (id uuid, title, package_id nullable, created_at, last_turn_at). Room documents are validated with the ported `room_contract` corner/opening rules before insert (`house_file.validate_room`). *Alternative:* one JSON document per owner; rejected because `room_fit` and the listing routes query by name and the next steps add writers.

5. **Pieces are recorded, versions are folders.** `create_piece` and `revise_package` write the version folder through the same `_create_version` path the package route uses (extracted into `app/packages/service.py` so both callers share it), then insert the `piece_versions` row in the same request. A package created directly through the route has no `pieces` row; the house file lists it from the folders as a piece without a brief (read-through), so the Designer still sees it.

6. **`revise_package` ports `revise_spec` verbatim** as `app/agent/revise.py` (`revise_spec(document, changes) -> (document, lines)`), reading the latest version's `input.json`. `PackageChanges` and `ModuleChange` move from the predecessor's `schemas.py` into this repo's `schemas.py`. The result is validated by `CustomBuildSpec` like any document, so an overlap or a bad thickness is refused the same way.

7. **Ladder step 2 recording.** `describe_validation_error` already names unknown fields as `<path>: Extra inputs are not permitted`; `create_piece`/`revise_package` detect that message shape, extract the field path, and insert a `generator_extension_requests` row with the owner's last human message as `request`. The tool's refusal text tells the Designer the request was recorded; the Designer's instruction file says what to tell the owner and forbids offering raw Blender code.

8. **`room_fit` is `normalise_room_scene` over house-file data.** It builds a room-scene document from the named room, the piece's `overall` (from the version's `spec.json`, else derived from `input.json`) and the given wall/offset with `output: {kind: still}`, runs the contract, and returns either the refusal text (already naming wall and excess) or `{placement, room_document}`. The Builder passes `room_document` to `render_turntable`'s `room` argument; the route code (`_room_document`) is reused for validation.

9. **Builder tools wrap the runner; builds wait, renders enqueue.** `blender_build` runs `runner.run_build` to completion on the app's event loop (`asyncio.run_coroutine_threadsafe(..., app.state.loop).result(timeout)`; the loop is captured in the lifespan) so the Builder can report the screenshot in the same turn (≈10 s). `render_turntable` quotes through `guard.quote`, interrupts for `final`, then `authorise` + `runner.mark_render_queued` + schedules `runner.run_render` on the loop and returns the estimate and the viewer route; draft and preview never block the turn. The semaphore, launch seam and tracing come from `app.state`. *Alternative:* enqueue builds too; rejected because the "screenshot → OK → render" step needs the screenshot in the reply.

10. **Chat routes and resumption.** `app/api/chat.py`: `POST /chat/threads {title?, package_id?}` → `{thread_id}`; `GET /chat/threads`; `GET /chat/threads/{id}` (messages from the checkpointer, pending confirmation from `graph.get_state(...).interrupts`); `POST /chat/threads/{id}/turns {message}`; `POST /chat/threads/{id}/resume {confirmation_id, answer, reason?}`. `thread_id` for the checkpointer is `chat:<thread uuid>`; `configurable` carries `thread_id`, `owner_id`, `package_id` — never from the model. A turn while an interrupt is pending → 409 naming the subject; a resume with a wrong id → 409. Responses are `{reply, specialist, pending: {confirmation_id, subject, summary, proposal} | null}`.

11. **What the homeowner sees.** The response model is the only exit: it has no field for models, tokens, cost or paths, and a test asserts no registry slug, no `tokens`, no `/home/` or render-root path appears in any reply for the fake-model scripts. Tool result text that must point at a file uses the package route form (`/packages/<id>/versions/<n>/files/<name>`).

12. **Prompts.** `app/agent/prompts.py` ports `SENTINEL`, `UNTRUSTED_CONTENT_PREAMBLE`, `compose_agent_prompt`, `neutralise`, `TOOL_ROUND_CAP_NOTE`, and adds `HOUSE_CONTEXT_PREAMBLE` and `house_note(...)` (rooms, preferences, pieces, open requests; every owner string neutralised). Retailer passage wrapping arrives with step 5. Instruction files: `foreman.md`, `intake.md`, `designer.md`, `builder.md` with headers `{name, slot, tools}`; the loader refuses an unknown tool, an empty text, the sentinel, or a slot not in routing.

13. **History bound in code.** With no budget yet, `agent` sends the system prompt plus the last `HISTORY_WINDOW = 40` messages (never splitting a tool call from its result); the checkpointer keeps the full thread. Step 7's budget replaces this.

14. **Tests.** `tests/fakes.py` ports `FakeChatModel` (tool-call scripts, bound-tool recording, structured output for the Foreman decision). Graph tests run with `InMemorySaver` and fake models per slot; route tests run against the test database with the real checkpointer and `fake_pipeline_launch`; one `--blender` test drives a turn that renders a `draft` turntable for real.

15. **Two readings fixed during apply.** (a) "A bound piece with a built version" for the Foreman's Builder rule means *a version exists* (queued, running, succeeded or failed): `create_piece` starts the build itself, so waiting for `succeeded` would make the Builder unreachable until the build ended. `blender_build` waits for a started build and re-runs a failed or unstarted one; `render_turntable` still refuses a version that has not succeeded. (b) `normalise_room_scene` checks the wall, ceiling and footprint but not openings, so `room_fit` adds the opening rule itself: a door is blocked by any piece in front of it, a window only when the piece is taller than its sill.

## Risks / Trade-offs

- [A real model may not follow the instruction files (asks for raw Blender, invents numbers)] → The tools refuse what the schema refuses, numbers reach the house file only through a confirmed `record_brief`, and the Builder has no tool that takes code; the `--live` suite is where prompt quality is checked, not the unit suite.
- [Blocking the HTTP turn for a build] → Bounded by `BLENDER_TIMEOUT_SECONDS`; a timeout is reported as a failed build, not a hung request. Renders never block.
- [Unbounded history without a budget] → Message-window trim in code; step 7 replaces it with the token budget.
- [Two threads revising the same piece] → Versions are numbered from the folder at write time under the request; the second gets the next number. No lock beyond that; one owner.
- [Interrupt ids change across resumes] → The pending id is always read from `get_state` at answer time and compared, as the predecessor did.

## Migration Plan

`uv run alembic upgrade head` adds the six tables; nothing existing changes. Package folders created before this change appear as pieces without a brief. Rollback: `alembic downgrade -1`; the checkpointer's threads are untouched.

## Open Questions

None that change the specs or tasks. The history window size and the Foreman's decision schema wording are assumptions recorded in code.
