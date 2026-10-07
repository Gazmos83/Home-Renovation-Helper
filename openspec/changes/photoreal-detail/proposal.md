## Why

The headless generators give truthful geometry, but they cannot add the carpentry detail, look-dev and lighting a photoreal `final` image needs. Those need the full `bpy` surface in a live Blender, which CLAUDE.md reserves for ladder step 3 behind the `bpy` allow-list (§8) and the render guard (§6). This is §11 step 8, plugin #8 `photoreal_detail` in §5, and it adds the **Lighting & materials** specialist that §3 names but the graph does not have yet.

## What Changes

- **Lighting & materials specialist** (new, on the existing `lighting` slot, `openai/gpt-5.6-sol`): the Foreman routes a turn to it only when the bound piece has a built version and the owner asks for photoreal detail, materials or lighting. It writes `bpy` scripts and works from a code-authored text scene report; it is text-only and never sees an image. It never changes the spec.
- **Live socket client** to the Blender MCP addon on `localhost:9876`, using the addon's JSON commands (`ping`, `execute_code`, `get_viewport_screenshot`). Any command is refused while a headless Blender job holds the Blender semaphore, and the client never queues behind one.
- **`bpy` allow-list** (§8): every script is parsed and checked before it reaches the socket, the backend's own included. `bpy.ops.wm.open_mainfile` is allowed only with a literal path equal to the pass's `detail.blend`. A refused script is named by its first offending construct and is never sent.
- **Detail pass on a version**: after the owner confirms, the backend copies the version's `model.blend` to `<version>/detail/detail.blend` and opens that copy in the live Blender. `model.blend` stays untouched. The Lighting agent then runs allow-listed scripts and the owner checks progress with viewport screenshots saved under `detail/screens/`. Every script, verdict and outcome goes to `detail/log.jsonl` and to Langfuse.
- **Detail render, `final` only**: `render_detail` renders `detail.blend` headless through the existing guard and runner at tier `final` (typed "yes" approval, Cycles) and publishes to `<version>/detail/` (`still.png` or `frames/` + `viewer.html`). `draft` and `preview` are refused for a detail render; progress is checked with screenshots.
- **Plugin** `backend/plugins/photoreal_detail/` with the tools `start_detail_pass`, `run_detail_script`, `detail_screenshot` and `render_detail`. Role `lighting`, toggleable.

**Ladder step and agent:** ladder step 3 only. A detail pass never writes a dimension or anything else back to the spec, and nothing reads `detail.blend` into the spec, cut list or pricing. Agents: Lighting & materials (new), Foreman (routing rule). **Render guard:** affected. A render can now read `detail.blend` instead of `model.blend`, and only at tier `final`, with the same ticket, approval, estimate and one-process rule. The live socket is refused while the headless semaphore is held. **bpy allow-list:** introduced by this change.

## Capabilities

### New Capabilities
- `photoreal-detail`: the live socket client, the `bpy` allow-list, the detail pass on a version (open, script, screenshot, log), the Lighting specialist's boundary, and the rule that the spec is never written back.

### Modified Capabilities
- `design-agents`: the Foreman may route to the Lighting & materials specialist, and that specialist runs on the `lighting` slot with its instruction file.
- `render-guard`: a render names its source (`model` or `detail`). A detail render is allowed only at tier `final`, and the ticket matches the source.
- `scene-rendering`: a detail render publishes into the version's `detail/` folder with the same layout and atomic publish.
- `furniture-packages`: the closed set of served file names gains the `detail/` names (render outputs and screenshots, never `detail.blend` or the log). It also states the `room/` names the code already serves.

## Impact

- Code:
  - New: `app/live/socket_client.py`, `app/live/allowlist.py`, `app/live/detail_pass.py`, `plugins/photoreal_detail/` (manifest + tool), `app/agent/instructions/lighting.md`.
  - Changed: `app/agent/foreman.py` (specialist + routing rule), `app/agent/models/slots.py` (`lighting` in `LOOP_SLOTS`), `app/render/guard.py` (quote/ticket `source`), `app/blender/runner.py` (detail source → `detail.blend`, target `detail/`), `app/blender/storage.py` (detail paths), `app/config.py` (`BLENDER_LIVE_HOST`/`PORT`, socket timeout).
- No migration: the pass's artifacts live in the version folder, which is gitignored like every render.
- Tests: the allow-list table (permitted and refused constructs, aliasing, dunder access, imports, `open_mainfile` with and without the pass's literal path), a socket client against a fake TCP server (refusal while the semaphore is held, connection refused, addon error), detail pass open/confirm/log, a `draft` detail render refused, a `final` detail render ticket and approval, a ticket for `model` refused for `detail`, Foreman routing, and the Lighting agent binding only its tools. The runner's detail path is tested with the fake launcher (argv names `detail.blend`, publish goes to `detail/`). No new real render is added to the `--blender` suite, because a detail render is `final`-only.
- Runtime dependency: the owner starts Blender 5.2.1 with the MCP addon (v1.6, already installed) listening on port 9876. Without it, the tools report that Blender is not open.
