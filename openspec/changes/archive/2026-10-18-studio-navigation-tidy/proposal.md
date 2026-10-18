## Why

The 15-10-2026 end-to-end review listed four small navigation irritations. The owner decided all of them on 2026-10-18:

1. **Sub-menu column.** The column beside the Design Studio rail lists the options of Workspace, Pieces, Measured Rooms, Model Library, Pricing, AI & Agent Settings and Design Knowledge. It stays open after an option is chosen. It should close automatically and have an "x" to close it.
2. **Turntable viewer link.** "Open the turntable viewer of <room>" shows on the Measured Rooms page itself. It should be reachable only from the room's inspector view (its 3D view).
3. **Tools button.** The Workspace's "Tools" button should go. When asked what should happen to the per-conversation plugin switches behind it, the owner chose "Drop per-chat toggles". Plugins are then switched only for the whole service, on the developer's Plugins page.
4. **Duplicate revision output.** A confirmed revision posts two notices, "X version N is created." with "Open version N" and later "X version N is built." with "Inspect version N". The owner said: keep "Inspect version N".

## What Changes

- **Sub-menu closes itself.** From 768 px wide, the sub-menu column gets a close button ("x") at its top. It closes when an entry is chosen, including "New conversation", and the content takes the freed width. Choosing a rail tab, even the current one, opens it again. A direct visit or reload shows it open. The phone row (below 768 px) is unchanged.
- **Turntable link only in the 3D view.** The Measured Rooms dialog drops its "Open the turntable viewer of <name>" link. The link appears inside the room's 3D view once that view is open. The Workspace room pane, the room inspector beside the chat, shows the same link for the chosen version.
- **BREAKING (behaviour): per-conversation tool switches are removed.**
  - Removed:
    - the Workspace "Tools" icon and flyout;
    - the owner routes `GET/PUT /chat/threads/{id}/tools[/{plugin}]`;
    - the per-thread enablement code;
    - the `thread_tool_settings` table, dropped by a migration.
  - A conversation now binds every globally enabled plugin.
  - The manifests keep `toggleable` (no manifest is edited). It stays visible on the Plugins page, but no longer affects binding.
  - CLAUDE.md §5 and the README are updated.
- **One notice per revision.**
  - `revise_package` stops posting the `revision` notice. The build notice with "Inspect version N" is the one notice.
  - Revision notices already in a thread show as text with no button.
  - While the build runs, the Piece icon (`workspace-opens-inspector`) opens the version.

Ladder: none of the three steps. This is Studio UI, one owner route removed and the plugin binding rule; no schema or generator change. Agents touched: none by prompt. Tool binding for every specialist now ignores per-thread settings. The **render guard** and the **bpy allow-list** are **not affected**.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-ui`:
  - the rail header without Tools;
  - the sub-menu column's close behaviour;
  - the Measured Rooms viewer link;
  - the build/revision notice display;
  - the tool-toggle requirement is removed and its other rules are kept as a new requirement.
- `plugins`: enablement is global only; the manifest's `toggleable` mark no longer affects binding.
- `homeowner-chat`: the thread tool-toggle requirement is removed; a revision posts no notice of its own.

## Impact

- **Frontend:**
  - `components/studio/SubMenu.tsx` and `routes/Studio.tsx` (open state, close button, close on choice, reopen on tab);
  - `routes/Rooms.tsx` (viewer link moved into the open 3D view);
  - `routes/Conversation.tsx`:
    - remove `Tools` and the `tools` rail entry;
    - add the viewer link in `RoomPane`;
  - `components/chat/Rail.tsx` (drop the `tools` icon key);
  - `components/chat/Notice.tsx` (no button on `revision`);
  - `lib/api.ts` (remove `tools`, `setTool`, `ToolToggle`);
  - tests: `SubMenu.test.tsx`, `Studio.test.tsx`, `Rooms.test.tsx`, `Conversation.test.tsx`, `Rail.test.tsx`.
- **Backend:**
  - delete `app/api/tool_toggles.py` and its router in `app/main.py`;
  - `app/plugins/enablement.py`: remove `thread_enabled`, `set_thread_enabled` and `list_thread_toggles`. `enabled_plugin_names` keeps its signature and ignores the thread;
  - docstring in `app/plugins/binding.py`;
  - remove `ThreadToolSetting` from `app/db/models.py`;
  - a new Alembic migration dropping `thread_tool_settings` (its downgrade recreates the empty table as in `0006`);
  - `plugins/revise_package/tool.py` stops calling `notices.post_revision`. `post_revision` and `revision_text` stay, for old history only, or are removed if unused;
  - tests: delete `tests/test_tool_toggles.py` and `tests/test_tool_toggles_api.py`, and adjust `tests/test_notices.py` and any binding tests that set thread toggles.
- **Docs:** CLAUDE.md §5 ("The homeowner toggles plugins per conversation…"), `README.md` (lines on per-conversation toggles), `docs/ENGINEERING_KNOWLEDGE.md` and `docs/kitchen_rag_migration_report.md` ("or per conversation").
- **Course requirement** ("a UI for the user to either enable or disable these function tools", `docs/Task requirements.md`): it is still met by the developer's Plugins page. TODO(user): confirm that this satisfies the course reviewer.
- **Order:** apply after `workspace-opens-inspector`. This change's rail requirement builds on that change's text.
