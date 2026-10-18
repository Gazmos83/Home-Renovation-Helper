## Context

`Conversation.tsx` already has approval controls in the Piece flyout (`PiecePanel`) and the Project flyout (`RoomSection`), both fixed to the latest version and driven by `progress`. The Workspace's `PiecePane` renders `InspectorView` for any chosen version; `RoomPane` renders `VersionSelect` + `RoomView` for any chosen composition version. The backend approves any built, recorded version and clears the other approval of that piece or composition (`house_file.approve_version`, `approve_composition_version`).

## Goals / Non-Goals

**Goals:** approve/unapprove the version a Workspace pane shows, with flyouts and pages kept in step.

**Non-Goals:** changing the flyouts' controls; adding approval to the stand-alone inspector page (`/pieces/.../inspect`); any backend change; deleting versions from the panes.

## Decisions

- **Shown version, not latest.** The pane's job is to show one version; approving what is on screen is what the owner expects, and it covers the case the flyouts cannot (an older version). Alternative — latest only, like the flyouts — would duplicate the flyout and leave older versions unapprovable from the Workspace.
- **Controls live in `PiecePane` / `RoomPane`, not in `InspectorView` / `RoomView`.** Those views are shared with the inspector page and the Rooms page, which have their own approval flows; putting the row in the panes keeps those pages unchanged.
- **Piece state from the `["version", packageId, version]` query** (the same one `InspectorView` uses, so they share the cache) for `status` and `approved_at`. **Room state from `progress.room`**: `versions[i].status` and `approved_version`.
- **One small shared component** `ApprovalRow` (label, approved?, built?, onApprove, onUnapprove, pending, error) in `frontend/src/components/`, used by both panes, so wording matches the flyouts ("Approved" badge, "Approve version N", "Unapprove version N"). The flyouts are left as they are (no refactor).
- **Invalidation** after success: piece — `["progress", threadId]`, `["version"]`, `["piece-versions", packageId]`, `["pieces"]`; room — `["progress", threadId]`, `["compositions"]`. Refusals use the existing `message(error)` helper and `FieldError`.

## Risks / Trade-offs

- [Two places approve the same thing in one screen (flyout and pane)] → identical wording and shared invalidation keep them consistent; flyout stays the "latest" shortcut.
- [Approving an older version silently unapproves the newer one] → that is existing behaviour of the route; the dropdown label updates at once so the change is visible.
