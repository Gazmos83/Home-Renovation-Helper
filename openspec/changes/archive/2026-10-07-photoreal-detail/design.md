## Context

See proposal.md for the motivation. What exists today:

- **Foreman graph.** Five specialists (`SPECIALISTS` in `app/agent/foreman.py`). The `lighting` slot is already routed (`openai/gpt-5.6-sol` in `config/models.yaml`) and named in `budget.py`, but it is not in `LOOP_SLOTS` and has no instruction file. `IMAGE_SLOTS = {intake, reviewer}` and stays so. The 2026-10-05 probe tested `openai/gpt-5.6-sol` with text only.
- **Render guard.** `quote` → `authorise` → single-use `RenderTicket` that matches `(package_id, version, kind, room, record)`. `run_render` launches `render_still.py` / `render_turntable.py` with `--blend <version>/model.blend`, verifies the staging folder and publishes atomically. Every Blender process shares `app.state.blender_semaphore = asyncio.Semaphore(1)`.
- **Live Blender.** The MCP addon (`~/.config/blender/5.2/scripts/addons/addon.py`, "MCP for Blender" v1.6) listens on `localhost:9876`. It takes one JSON object `{"type": <command>, "params": {...}}` per request and answers `{"status": "success", "result": ...}` or `{"status": "error", "message": ...}`. Relevant commands: `ping`, `execute_code(code)`, which runs `exec(code, {"bpy": bpy})` and returns captured stdout, and `get_viewport_screenshot(max_size, filepath, format)`. The addon's own policy allows anything, so every check must happen in the backend.
- **File serving.** The version file route serves a closed set of names. It already serves `room/…`, which the `furniture-packages` spec does not list; this change adds that to the spec as well.

## Goals / Non-Goals

**Goals:**
- A confirmed, logged, allow-listed live pass on a copy of a version's model, ending in an approved Cycles `final` render published beside the version.
- Make it structurally impossible for step 3 to change the spec or to render outside the guard.

**Non-Goals:**
- Camera matching against room photos and detail passes on apartment shells (later; same machinery).
- Room renders of a detailed piece. A detail render is the piece alone.
- Image textures loaded from disk, asset-library imports (Poly Haven and similar) and generated 3D models. Materials are procedural node graphs. Each excluded item would be its own change.
- Running the live Blender for the owner. The owner opens it.

## Decisions

1. **The pass works on a copy.** `start_detail_pass(version)` is a confirmation (`interrupt()`, same `Confirmation` shape as `revise_package`). Its summary says the open Blender file will be replaced. On `yes`, the backend copies `model.blend` to `<version>/detail/detail.blend` if it does not exist yet, so a second pass continues the first. It then sends a fixed, code-authored script that opens that file. `model.blend`, `spec.json` and the cut list are never opened for writing. *Alternative:* edit `model.blend` in place. Rejected: a rebuild would overwrite the detail, and the headless renders would stop matching the spec.

2. **Every script goes through the allow-list, the backend's own included.** Two kinds of script reach the socket, and both are checked:
   - **Fixed templates** are string constants in `app/live/detail_pass.py`: open the file, assert the open file, save, and report the scene. They take only a path that `storage.resolve` has checked under the version's `detail/` folder, inserted with `repr()`.
   - **Model-authored scripts** are what the Lighting agent writes.

   The allow-list is given the pass's `detail.blend` path on each call. It permits `bpy.ops.wm.open_mainfile(filepath=<literal>)` only when that literal equals the path (decision 3), which is what the open template needs. Decided by the owner: this keeps §8 ("every live bpy script goes through the allow-list") literally true. Before each model script, a template asserts that `bpy.data.filepath` is the expected `detail.blend`. If the owner opened another file, the script is not run and the agent is told the pass was interrupted.

3. **The allow-list is a static AST check** (`app/live/allowlist.py`, pure, no `bpy`). It returns `Allowed` or `Refused(construct, line)`. Rules:
   - The source must parse, be at most 20 000 characters, and contain no `global`/`nonlocal` statements and no `async` code.
   - **Imports:** only `bpy`, `bmesh`, `mathutils`, `math` and `random`. `os`, `subprocess`, `shutil`, `sys` and every other module are refused by name.
   - **Builtins refused:** `open`, `exec`, `eval`, `compile`, `__import__`, `globals`, `locals`, `vars`, `getattr`, `setattr`, `delattr`, `input`, `breakpoint`, `memoryview`. §8 allows `open()` inside `docs/renders/` and the package folder, but a static check cannot prove where a path points, so `open` is refused outright. This is stricter than §8.
   - **Attributes:** any dunder attribute is refused. These attribute names are refused on any base, which also defeats aliasing (`d = bpy.data; d.texts`): `texts`, `libraries`, `app`, `utils`, `handlers`, `timers`, `preferences`, `addons`, `load`, `save`, `save_as`, `save_render`, `unpack`, `filepath_raw`, `as_module`, `driver_namespace`.
   - **Operators:** `bpy.ops` may appear only as a direct call `bpy.ops.<ns>.<op>(...)` with `<ns>` in `{mesh, object, material, node, uv, transform}`. There are two exceptions: `bpy.ops.wm.save_mainfile()` with no arguments, which saves the open `detail.blend`, and `bpy.ops.wm.open_mainfile(filepath=<string literal>)` with no other argument, allowed only when the literal is exactly the pass's `detail.blend` path. A variable, an expression, another path or an extra argument is refused naming `bpy.ops.wm.open_mainfile`. The agent may call it too, but it can only reopen the same file. Any other use of `bpy.ops`, including binding it to a name, is refused as `bpy.ops.<ns>.<op>`. This refuses `bpy.ops.render.*`, so nothing renders outside the guard.
   - **Permitted:** `bpy.data.*` (objects, meshes, materials, node groups, worlds, lights, cameras), modifiers, material and world node trees, and `scene.render.*` / `scene.cycles.*` / `scene.eevee.*` assignments. The detail render's generator re-applies the tier's engine, resolution and frames, so a script cannot change what the guard quoted.

   The allow-list is a guard against agent mistakes, as DESIGN_NOTES says; it is not a sandbox. The risks section covers this.

4. **The socket client** (`app/live/socket_client.py`) opens one TCP connection per command to `BLENDER_LIVE_HOST:BLENDER_LIVE_PORT` (default `127.0.0.1:9876`; a non-loopback host is refused at startup). It sends the JSON object and reads until it has one complete JSON value, with a 120 s cap per command. Before connecting it calls `semaphore.locked()`. If a headless job holds the semaphore, the command is refused with "a Blender job is running; try again when it finishes". Otherwise it holds the semaphore for the duration of the command, so a headless build queues behind a running script instead of overlapping it. Connection refused → "Blender is not open with the MCP addon". An addon `error` → the message is passed to the agent as delimited untrusted content.

5. **Screenshots.** `detail_screenshot` calls `get_viewport_screenshot(max_size=800, filepath=<detail/screens/NNN.png>, format="png")` with the path chosen by code. The image is served to the owner through the file route. The Lighting slot stays **text-only** (decided by the owner): `lighting` is not in `IMAGE_SLOTS` and no image block ever reaches its model. After each script, a code-authored scene report (objects, materials and modifiers per object, world and lights, as text and delimited as untrusted) goes back to the agent, and the owner judges the screenshots. The agent asks the owner to look when a visual judgement is needed.

6. **Log.** `detail/log.jsonl` holds one line per script: time, purpose (the agent's one-line statement), the code, the verdict (allowed or refused with construct and line), the outcome (ok or error with message) and the duration. The same fields minus the code go to Langfuse as a `detail_script` event. The code goes as event input, because scripts are not secrets.

7. **Detail render.** `render_detail(version, kind, tier)` reuses `render_turntable`'s guard path with `source="detail"`:
   - `RenderQuote` gains `source: Literal["model","detail"] = "model"`, and `RenderTicket.matches` compares it.
   - `quote()` refuses `source="detail"` unless the tier is `final` ("a detail render is final only; check progress with a screenshot") and refuses `room=True` with a detail source.
   - `run_render` picks `--blend <version>/detail/detail.blend` and publishes to `<version>/detail/`. The status keys are `detail-still` and `detail-turntable`, added to `storage.RENDER_KEYS`.
   - Before rendering, a fixed template saves the live file. If the live Blender is closed, `detail.blend` on disk is used as it is.
   - Calibration of the Cycles multiplier applies to a detail final like any final.

8. **Routing.** `load_house` computes `detail_ready` (the bound piece's latest version has `model.blend`). The Foreman never chooses `lighting` without it, and falls back by the existing rules. `lighting.md` header: `slot: lighting`, `tools: [start_detail_pass, run_detail_script, detail_screenshot, render_detail]`. The Lighting agent has no `create_piece`, `revise_package` or `render_turntable`. Asked to change a size, it says the Designer changes dimensions.

9. **Files served.** The closed set grows by `detail/still.png`, `detail/viewer.html`, `detail/scene.json`, `detail/frames/<index>` and `detail/screens/<index>`. It never includes `detail/detail.blend` or `detail/log.jsonl`. The log reaches the developer only through Langfuse.

## Risks / Trade-offs

- [A crafted script escapes the static check through Python introspection that the rules miss] → The agent is the only author and its inputs are delimited. The check refuses the known escape routes (dunders, `getattr`, imports, `bpy.app`, `texts`). The owner can switch the plugin off. The addon runs as the owner's user, and the allow-list does not change that.
- [The owner edits the live file during a pass] → The filepath assertion before every script. The owner's own edits are theirs to keep.
- [CPU contention between the live Blender and a headless job] → Socket commands are refused while a job runs. A headless job queued during a script waits for it.
- [Long scripts freeze the Blender UI] → 120 s cap per command. The addon runs on Blender's main thread, so a timeout leaves Blender busy, and the client reports it rather than retrying.
- [Cycles finals are slow on this CPU] → This is the existing guard estimate and approval. Offload is `render-offload`.

## Migration Plan

No database change. New settings `BLENDER_LIVE_HOST` and `BLENDER_LIVE_PORT` have defaults. Rollback: disable the `photoreal_detail` plugin globally. Existing `detail/` folders are inert.
