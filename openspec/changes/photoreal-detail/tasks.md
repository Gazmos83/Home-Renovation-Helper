## 1. Allow-list

- [x] 1.1 Write `app/live/allowlist.py` (pure AST check, design decision 3). Verify a table test `tests/test_live_allowlist.py` covers every spec scenario plus: each refused import and builtin; dunder access; `bpy.ops` bound to a name; each refused attribute on an aliased base; `save_mainfile()` allowed but not with arguments; `open_mainfile` allowed only with the pass's literal path (refused for `model.blend`, a variable, an extra argument); the 20 000-character cap; a syntax error; a material/modifier/world script allowed

## 2. Socket client and detail pass

- [x] 2.1 Add `BLENDER_LIVE_HOST`/`BLENDER_LIVE_PORT` settings (non-loopback refused at startup) and `app/live/socket_client.py` (one connection per command, 120 s cap, semaphore check and hold). Verify `tests/test_live_socket.py` against a fake TCP server covers success, an addon `error` delimited as untrusted, connection refused, refusal while the semaphore is held, a headless job waiting while a command holds it, and `tests/test_config.py` covering a non-loopback host refused
- [x] 2.2 Add detail paths to `app/blender/storage.py` and write `app/live/detail_pass.py` (fixed templates for open, filepath assert, save and scene report, all sent through the allow-list; copy-on-first-pass; numbered screenshots; `log.jsonl`; Langfuse `detail_script` event). Verify `tests/test_detail_pass.py` (fake client) covers every template passing the allow-list, the scene report returned as text, first pass copying `model.blend` byte-for-byte, a second pass keeping the copy, the filepath mismatch stopping a script, the log line for allowed and refused scripts, and tracing off/failing not affecting the pass
- [x] 2.3 Create `plugins/photoreal_detail/` (manifest: role `lighting`, toggleable, enabled by default; tools `start_detail_pass` with confirmation, `run_detail_script`, `detail_screenshot`, `render_detail`). Verify `tests/test_plugin_manifest.py` loads it and `tests/test_photoreal_detail.py` covers the confirmation `yes`/`no`, an unbuilt version refused, and no model-generated path accepted

## 3. Guard and runner

- [x] 3.1 Add `source` to `RenderQuote`/`RenderTicket.matches`. In `quote()`, refuse a detail source below `final`, with a room, or without `detail.blend`. Verify `tests/test_render_guard.py` covers detail at tier `draft` and `preview` refused, at tier `final` raising `ApprovalRequired` with the 36-frame Cycles estimate, and a `model` ticket refused for a `detail` launch
- [x] 3.2 Teach `run_render` the detail source (argv `--blend detail/detail.blend`, publish to `detail/`, `scene.json` source `detail`, save-before-render template when the socket answers). Verify `tests/test_runner.py` with the fake launcher at tier `final` covers argv, publish target, the version's own `frames/` untouched, the save attempted, and a closed Blender not blocking the render
- [x] 3.3 Extend the version file route to the `detail/` names, never `detail.blend` or `log.jsonl`. Verify `tests/test_packages_api.py` covers `detail/screens/<i>` served, `detail/detail.blend` and `detail/log.jsonl` not found, and the `room/` names still served

## 4. Lighting specialist

- [x] 4.1 Add `lighting.md` (role, rules: one purpose line per script, work from the scene report, ask the owner to look at the screenshot for visual judgements, never change dimensions, final render only on request) and add `lighting` to `SPECIALISTS`, `LOOP_SLOTS`, the Foreman's decision and the `detail_ready` rule. Verify `tests/test_foreman.py` covers routing to Lighting for a built piece, never without a build, the binding of exactly the four detail tools, `lighting` absent from `IMAGE_SLOTS` and no image block reaching its model, and `tests/test_instructions.py` covering the header
- [x] 4.2 Loop test (fake models, fake socket): confirm pass → allowed script → screenshot → `render_detail` at tier `final` interrupts with the estimate → `yes` starts one guarded run. Verify `tests/test_detail_loop.py` passes and that no spec, cut list or version record changed

## 5. Verification

- [x] 5.1 Manual check with the live Blender 5.2.1 and addon: start a pass on a fixture piece, run one allowed material script and one refused script, take a screenshot, and confirm `model.blend` is unchanged. No render in this check. Record the outcome in the commit message
- [x] 5.2 README (starting a detail pass, what the allow-list refuses) and CLAUDE.md §5 #8 status / §11 step 8 tick
- [x] 5.3 Run `uv run ruff check .`, `uv run pytest -m "not slow"` and `uv run pytest --blender -m blender` (existing renders stay at tier `draft`; no new real render). Verify all pass and record the counts in the commit message
