## Context

See proposal.md (Why). The current state:

- **Chat pane header.** `ChatPane` in `frontend/src/routes/Conversation.tsx` renders `<Rail variant="row">` with six panels. Each has flyout `content`:
  - Piece → `PiecePanel`: approval, version-limit notice, `DeleteVersion` for the latest version, picture, "Inspect version N", `PieceVariants`, open generator-extension requests;
  - Room → `RoomPanel` / `RoomSection`: approval, `DeleteCompositionVersion`, approved picture, `RoomVariants`, "Inspect <room>".
- **Panes already approve.** `PiecePane` and `RoomPane` already render `ApprovalRow` (`workspace-pane-approval`). The approve control the owner missed exists in two places, and the flyout is the one they found.
- **Opening a pane.** `useConversation` exposes `inspect(packageId, version)` and `inspectRoom(slug)`. Both call `showPane`. `ConversationWorkspace` (`frontend/src/routes/Workspace.tsx`) then switches the layout, or the phone tab, when the pane is not shown.
- **Polling.** `progress` uses `refetchInterval` only for `build_status` queued/running or `rendering`. A composition build sets neither, so `progress.room.versions[0].status` stays "queued" in the room pane until another refetch.
- **Refusals.** They arrive as `ApiError.message`, built from the route's `detail.reason`. They are already sentences ("… places listening-wall, which is not approved; approve those piece versions first").
- **Spec drift.** `split-project-panel` (archived) introduced the Piece and Room flyouts, but its delta was never synced into `openspec/specs/studio-ui`. The main spec still speaks of "the Project panel" for piece and room controls. This change does not re-sync that archive. Instead, its MODIFIED pane requirement states that such references now mean the panes.

## Goals / Non-Goals

**Goals:**
- One place per thing: the pane that shows a version is where it is approved, deleted and restyled.
- No regression: every control the flyouts offered stays reachable.
- A fresh composition version becomes approvable without a reload.

**Non-Goals:**
- Changing the Pieces page, the Measured Rooms page or the standalone inspector page (`/pieces/<id>/versions/<n>`).
- Changing approval rules or backend routes.
- Removing the Tools flyout (that is `studio-navigation-tidy`).

## Decisions

1. **Rail entries may be actions.** `Panel` gains an optional `onSelect?: () => void`, and `content` becomes optional. An entry with `onSelect` renders the same icon button with the same name, tooltip and label behaviour. Clicking it calls `onOpen(null)` (closing any flyout) and then `onSelect()`. It never sets `aria-expanded`.
   - Rejected: a separate button group beside the rail. It would break the header's single icon row and the label switch that the spec requires.

2. **What the icons do.**
   - Piece: `c.inspect(p.package_id, p.latest_version)` when both are known. Otherwise `showPane("piece")` directly, so the pane's own empty state shows. `useConversation` returns `showPane` for this.
   - Room: `c.inspectRoom(room.slug)` when a composition exists. Otherwise `showPane("room")`.
   - The address rules stay as they are (`?inspect=`, `?room=`).

3. **Moving the flyout blocks.**
   - `PiecePane`: after the `ApprovalRow`, add:
     - the build-state badge (from `info.data.status`);
     - the version-limit line (from `progress`);
     - `DeleteVersion` for the **shown** version. The Pieces page already deletes the shown version, and the pane can show any version. Hidden while approved, queued or running;
     - `PieceVariants` with `onUse → c.send(keepLookRequest(...))`;
     - the open-requests list (from `progress.open_requests`).
   - `RoomPane`: `DeleteCompositionVersion` for the chosen version when it is not approved, and `RoomVariants` when that version succeeded. The approved-picture thumbnail is not moved, because the pane already shows the 3D model.
   - The `PiecePanel`, `RoomPanel` and `RoomSection` components are deleted. Their mutations are already duplicated in the panes.

4. **Room-build polling.** `refetchInterval` also returns 3000 while `query.state.data?.room?.versions?.[0]?.status` is "queued" or "running". The thread query's `following` flag includes the same condition, so a room-render or build notice arrives without a reload.
   - Rejected: polling `["compositions"]`. The pane reads `progress`, not the compositions list.

5. **Refusals.** `ApprovalRow` already shows `message(error)`, the service's reason. No mapping layer is added: the reasons are written for the owner already, and the spec only forbids codes, which `ApiError.message` never contains.

## Risks / Trade-offs

- [Owners used the flyout to glance at a piece without changing the layout.] → Opening a pane switches the layout, as "Inspect" always did. The flyout's picture is replaced by the live 3D view.
- [Delete in the pane targets the shown version, where the flyout used the latest.] → The confirmation names the version number, and approved or building versions offer no delete.
- [Extra polling while a composition builds.] → The same 3 s interval as piece builds, and only while queued or running.

## Migration Plan

Frontend only, with no data change. Rolling back means reverting the commit.
