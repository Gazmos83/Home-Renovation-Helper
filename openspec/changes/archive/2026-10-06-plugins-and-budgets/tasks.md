## 1. Plugins

- [x] 1.1 Add `app/plugins/{manifest,loader}.py` (manifest model, folder loading, errors naming the file, tool → plugin map) and migration `0006_plugins_budgets`; verify `tests/test_plugin_manifest.py` covers each refused field, a duplicate tool naming both files, an unknown role, and upgrade/downgrade without drift
- [x] 1.2 Move each built-in tool group into `backend/plugins/<name>/{manifest.yaml,tool.py}` (intake, create_piece, revise_package, cut_list, room_fit, guidelines, blender_build, render_turntable, material_cost, catalog_research, revision_review) and derive `KNOWN_TOOLS` and the instruction loader's tool set from the manifests; verify the full suite still passes after the move and at least ten tools are toggleable
- [x] 1.3 Port the HTTPS kind (`https_schema`, `executor` with SSRF guard, pinned IP + SNI, no redirects, cap, timeout, pacing, untrusted wrapping, invocation audit) with `PLUGIN_*` settings; verify `tests/test_plugin_executor.py` covers a private address refused, a redirect refused, an oversized body, a timeout, an undeclared output field dropped, the audit row without arguments, and a failure returned as text

## 2. Enablement

- [x] 2.1 Add global (`plugin:<name>`) and per-thread enablement and the binding rule in the graph (`bound_tools` computed in `load_house`); verify `tests/test_tool_toggles.py` covers a tool switched off in one thread only, a non-toggleable plugin refused, a globally disabled plugin hidden from the thread, and a resumed confirmation keeping the turn's tools
- [x] 2.2 Add `GET/PUT /chat/threads/{id}/tools`; verify `tests/test_tool_toggles_api.py` covers defaults, a change applying from the next turn, 409 cases, and no model or token in the body

## 3. Token budget

- [x] 3.1 Port `app/agent/budget.py` (counting with images, trimming, too-large refusal) and add the daily ceiling with `estimated_tokens` on usage rows; replace `window()` in every node; verify `tests/test_budget.py` covers a long thread trimmed with the note and the stored thread unchanged, a too-large message refused with no call, a tool call never split from its result, and the ceiling refusing across two turns
- [x] 3.2 Wire the refusal reply by role; verify `tests/test_chat_budget.py` shows the Designer's daily refusal as a 200 reply naming the Designer, nothing pending, and no slug or token figure

## 4. Developer panel

- [x] 4.1 Add `/admin/models`, routing, generation and budget routes with probe-before-switch and live swaps; verify `tests/test_admin_models_api.py` covers a probed switch applying to the next call, a failed probe refused with routing unchanged, reset to the file, an out-of-range value refused naming the field, a lowered ceiling taking effect, and 404 with the panel disabled
- [x] 4.2 Add `/admin/plugins` (list, enable/disable, invocations) and `/admin/usage`; verify `tests/test_admin_plugins_api.py` and `tests/test_admin_usage_api.py`

## 5. Studio pages

- [x] 5.1 Add the conversations page with tool toggles; verify component tests and a browser pass recorded here (toggle off, a non-toggleable tool shown always on)
  Browser pass: `Conversations.test.tsx` — toggle `room_fit` off; `create_piece` shown always on and disabled. No live browser MCP in this session.
- [x] 5.2 Add the developer pages (models and routing, generation and budgets, plugins, usage) on `/admin/*`, hidden when the API answers 404; verify component tests and a browser pass recorded here (a probed switch, a refused value next to its field, a plugin disabled, usage shown)
  Browser pass: `Models.test.tsx` (refused probe next to the slot, refused daily ceiling next to its field), `Plugins.test.tsx` (plugin disabled), `Usage.test.tsx` (today's totals). Admin nav is mounted only after `GET /admin/models` succeeds. No live browser MCP in this session.

## 6. Documentation and verification

- [x] 6.1 README: plugin folders and manifests, HTTPS plugins and the allow-list, toggles, token restrictions, the developer panel; CLAUDE.md §5 and §11 step 7 ticked
- [x] 6.2 Run `uv run ruff check .`, `uv run pytest -m "not slow"`, `uv run pytest --blender -m blender` (no render added; every render at `draft`), and `pnpm lint && pnpm test && pnpm build`; verify all pass and record the counts in the commit message
  Counts: ruff clean; pytest `-m "not slow"` 731 passed, 24 skipped; pytest `--blender -m blender` 23 passed (draft only); frontend 6 tests, oxlint 0 errors, `pnpm build` ok.
