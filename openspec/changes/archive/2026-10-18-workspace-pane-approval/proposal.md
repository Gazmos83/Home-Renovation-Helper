## Why

In the Workspace the owner looks at a piece in the piece pane and at the room in the room pane, but to approve what they see they have to open the Piece or Project flyout over the chat. Those flyouts only approve the latest version, so a version picked in a pane's dropdown cannot be approved from where it is shown at all. The owner asked on 2026-10-17 for an approve button in the Workspace's room and piece views.

## What Changes

- The Workspace's **piece pane** gains an approval row above the inspector for the version it shows: "Approved" when that version is approved, "Approve version N" when it is built and not approved, "Unapprove version N" when it is the approved one. Approving it clears another approved version of the piece, as approval already does.
- The Workspace's **room pane** gains the same row for the composition version it shows, beside its version dropdown.
- A refusal (not built, not recorded, unapproved placed pieces, a piece placed in an approved room) is shown in plain words next to the control.
- After a change the pane, its version dropdown ("approved" label), the Piece and Project flyouts, the Pieces page and the Rooms page show the new state without a reload.
- The flyouts keep their own controls unchanged. The stand-alone inspector page is unchanged.

Ladder: none of the three steps; UI-only, using the existing approval routes. No agent is touched. The **render guard** and the **bpy allow-list** are **not affected**: approving never renders.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-ui`: a new requirement that the Workspace's piece pane and room pane show and set approval for the version they show.

## Impact

- `frontend/src/routes/Conversation.tsx` (`PiecePane`, `RoomPane`), possibly a small shared approval-row component under `frontend/src/components/`.
- `frontend/src/routes/Workspace.test.tsx` gains tests.
- No backend, API, schema or migration change: `PUT/DELETE /packages/{id}/versions/{n}/approval` and `/compositions/{slug}/versions/{n}/approval` already approve any built, recorded version.
