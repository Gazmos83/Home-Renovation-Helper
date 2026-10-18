## Context

See proposal.md (Why). The current state:

- **Sub-menu.** `Studio.tsx` renders `<SubMenu layout="column">` (hidden below `md`) and `<SubMenu layout="row">` (hidden from `md`). Their entries are `<Link>`s; "New conversation" is a `lead` button. There is no open/closed state.
- **Viewer link.** `Rooms.tsx` `CompositionCard` shows "Open the turntable viewer of {name}" whenever `shown.viewer` is set, outside the `open3d` branch. `RoomPane` shows no viewer link, although `progress.room.versions[].viewer` carries it.
- **Per-thread toggles.**
  - `app/plugins/enablement.py` holds the global keys (`plugin:<name>` in `operator_settings`) and per-thread rows (`thread_tool_settings`, migration `0006`).
  - `enabled_plugin_names(session, plugins, thread_id)` is the single binding entry. It is used by `app/plugins/binding.py` and by `app/api/chat.py`, which uses it for engineering trace suppression.
  - `app/api/tool_toggles.py` serves the owner routes, and the `Tools()` flyout calls them.
- **Notices.** `revise_package` calls `notices.post_revision` once a version is recorded. `blender_build`, `create_piece` and `revise_package` reach `post_build` through `follow_build`. `Notice.tsx` renders "Open version N" for `kind == "revision"`.

## Goals / Non-Goals

**Goals:** the four owner decisions, with no leftover dead route, table or UI.

**Non-Goals:**
- Changing the phone sub-menu row.
- Changing which plugins are enabled by default.
- Editing the 25 manifests to drop `toggleable`.
- Deleting old revision notices from threads.

## Decisions

1. **Sub-menu open state lives in `Studio`.**
   - `const [menuOpen, setMenuOpen] = useState(true)`.
   - `SubMenu` gains `onClose?: () => void` (renders the "x" button, `aria-label="Close <label>"`, column layout only) and `onChoose?: () => void` (called by every entry link and by the `lead`).
   - The column renders only while `menuOpen`.
   - Each rail tab `Link` gets `onClick={() => setMenuOpen(true)}`, so choosing the current tab reopens the column.
   - The row layout ignores both props.
   - The state is not remembered across reloads, so a reload shows the column.
   - Rejected: storing it in localStorage. A remembered closed column would hide the conversation list on the next visit.

2. **Viewer link placement.**
   - In `CompositionCard`, move the link inside the `open3d` branch, under `RoomView`.
   - In `RoomPane`, render the same link under `RoomView` when `chosen.viewer` is set.
   - "Inspector view" is read as the room's 3D view, on the Measured Rooms page and beside the chat. TODO(user): confirm.

3. **Dropping per-thread toggles.**
   - `enabled_plugin_names` keeps the `thread_id` parameter, so the call sites stay unchanged, but returns the globally enabled plugins only.
   - `thread_enabled`, `set_thread_enabled`, `list_thread_toggles`, `ToolToggle` and `EnablementRefused` are removed with the router. `EnablementRefused` is removed only if nothing else imports it.
   - The table is dropped, not kept. It holds nothing else, nothing references it, and keeping an unused table would mislead.
   - The migration's downgrade recreates the table empty, as `0006` defined it. The revision number is the next free one when applied, because other batch changes may add migrations first.
   - **Consequence:** `engineering_knowledge` and `engineering_calculators` were documented as "opt in per conversation". Once globally enabled, they now apply to every conversation. Both default to off, and enabling them is a developer action gated by the release checks in `admin_plugins.py`. The docs are updated to say "globally".

4. **One notice per revision.**
   - Remove the `post_revision` call in `revise_package/tool.py`. If nothing else calls `post_revision` or `revision_text`, remove them too.
   - `Notice.tsx` keeps rendering `revision` notices as text with no button (old history).
   - Rejected: keeping the revision notice text-only for new revisions. That still shows two lines per revision, which is the duplication the owner flagged.
   - Rejected: replacing the revision notice in place when the build ends. It needs an update path for notices that does not exist.

## Risks / Trade-offs

- [No link to a new version until its build ends (about 30 s)] → The Piece icon opens the latest version straight away (`workspace-opens-inspector`). The inspector shows the build state and follows the version when it is built.
- [The course requirement asks for a UI to enable or disable tools] → The developer's Plugins page is that UI. Flagged TODO(user) in the proposal.
- [Owners who had switched a plugin off in one conversation get it back] → Accepted by the owner's decision. The release notes in the README say so.

## Migration Plan

Run `uv run alembic upgrade head`; the new revision drops `thread_tool_settings`. To roll back, downgrade one revision (the empty table is recreated) and revert the commit. Stored per-thread choices are not restored.
