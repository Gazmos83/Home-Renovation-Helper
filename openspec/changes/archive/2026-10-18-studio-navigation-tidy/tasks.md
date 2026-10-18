## 1. Sub-menu column

- [x] 1.1 In `frontend/src/components/studio/SubMenu.tsx`, add `onClose` (an "x" button "Close <label>" at the column's top) and `onChoose` (called by every entry and the lead), both for the column layout only. In `frontend/src/routes/Studio.tsx`:
  - keep `menuOpen` state, open at first;
  - render the column only while it is open;
  - close it on a choice or on the "x";
  - reopen it on any rail tab click.
  Verify with `SubMenu.test.tsx` and `Studio.test.tsx` cases for "Sub-menu closes after a choice", "Sub-menu closed with its x", "Sub-menu reopened from the rail" and "Row unchanged on a phone".

## 2. Turntable viewer link

- [x] 2.1 In `frontend/src/routes/Rooms.tsx`, move "Open the turntable viewer of <name>" into the open 3D view branch. In `RoomPane` (`frontend/src/routes/Conversation.tsx`), show the same link under the room view when the chosen version has a viewer. Verify with `Rooms.test.tsx` ("Turntable viewer only in the 3D view") and a Conversation test for the pane link.

## 3. Drop per-conversation tool switches

- [x] 3.1 Frontend:
  - remove `Tools()` and the `tools` rail entry from `Conversation.tsx`;
  - remove the `tools` icon key from `Rail.tsx`;
  - remove `tools`, `setTool` and `ToolToggle` from `lib/api.ts`;
  - update `Rail.test.tsx` and `Conversation.test.tsx`.
  Verify with a Conversation test "No Tools icon" and `pnpm lint` (no dangling imports).
- [x] 3.2 Backend:
  - delete `app/api/tool_toggles.py` and its `include_router` in `app/main.py`;
  - in `app/plugins/enablement.py`, keep `global_enabled`, `set_global_enabled` and `enabled_plugin_names` (global only, `thread_id` ignored) and remove the per-thread functions;
  - update the `binding.py` docstring;
  - remove `ThreadToolSetting` from `app/db/models.py`;
  - delete `tests/test_tool_toggles.py` and `tests/test_tool_toggles_api.py`;
  - add a test that a globally enabled toggleable plugin is bound in every thread and a globally disabled one in none.
  Verify with `uv run ruff check .`.
- [x] 3.3 Add an Alembic migration (next free revision) that drops `thread_tool_settings`; its downgrade recreates it as in `0006`. Verify with `uv run alembic upgrade head` and `downgrade -1` on a throwaway database.
- [x] 3.4 Update the docs:
  - CLAUDE.md §5 sentence on homeowner toggles → "The developer enables or disables plugins globally from `/admin/plugins`; there are no per-conversation switches.";
  - `README.md` (lines on per-conversation toggles and the toggle curl example);
  - `docs/ENGINEERING_KNOWLEDGE.md` and `docs/kitchen_rag_migration_report.md` ("or per conversation").
  Verify with `grep -rn "per conversation" CLAUDE.md README.md docs/*.md`, which should return no plugin-toggle line.

## 4. One notice per revision

- [x] 4.1 Remove the `notices.post_revision` call in `backend/plugins/revise_package/tool.py`. Remove `post_revision` and `revision_text` from `app/agent/notices.py` if nothing else uses them, and update `tests/test_notices.py`. In `frontend/src/components/chat/Notice.tsx`, render `revision` notices as text with no button. Verify with a notices test "No separate revision notice" and Conversation tests "One notice per revision" and "Old revision notice", replacing the existing "Open version 1" test.

## 5. Checks

- [x] 5.1 Run `uv run ruff check .` in `backend/` and `pnpm lint`, `pnpm test` and `pnpm build` in `frontend/`; all must pass. pytest is deferred to the batch check after the last change of the 2026-10-18 review batch (skip the RunPod/offload tests, use a throwaway `TEST_DATABASE_URL`).
- [x] 5.2 Browser pass, **no render tier**, at 1280 × 800 and 360 × 780:
  - choosing a sub-menu entry closes the column, its "x" closes it, and the rail tab reopens it;
  - the Measured Rooms dialog shows the viewer link only inside the open 3D view;
  - the room pane shows the viewer link;
  - the Workspace has no Tools icon;
  - a confirmed revision shows one notice with "Inspect version N".
