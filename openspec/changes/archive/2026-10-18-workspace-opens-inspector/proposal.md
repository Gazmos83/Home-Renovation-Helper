## Why

In the 15-10-2026 end-to-end review the owner could not approve a revised piece or room from the Workspace, and called the flow a flawed UI experience. The Piece and Room icons in the chat pane header open a flyout over the chat. The approve control the owner looked for sits in that flyout, apart from the 3D view it is about. The owner's decision of 2026-10-18: "The Piece and Room button from the Workspace view (in the conversations window) should not have a pop up. … Instead, remove the pop up window and automatically open the inspector view. Provide the option to approve in the inspector view."

A second fault makes this worse. The conversation's progress is polled only while a piece build or a render runs. A freshly composed room version therefore stays "queued" in the room pane, with no Approve button, until something else refreshes the page.

## What Changes

- **No Piece or Room flyout.** In the Workspace chat pane header, the Piece and Room icons stop opening a flyout and open the matching pane instead:
  - **Piece** shows the piece pane (the inspector) at the bound piece's latest version, switching the layout as "Inspect version N" does today;
  - **Room** shows the room pane (the room's 3D view) at the room's latest composition version, switching the layout as "Inspect <room>" does today;
  - on a phone, each icon switches to its pane's tab.
  With no piece, or no confirmed room, the pane opens and says so in plain words, as it already does.
- **Everything the flyouts held moves into the panes**, so nothing is lost:
  - **Piece pane:**
    - the piece's build state;
    - "N of 15 versions" near the limit;
    - "Delete version N" for the shown version, when it is not approved and not building;
    - the restyle looks with "Keep this look";
    - the open generator-extension requests.
  - **Room pane:**
    - "Delete version N" for the shown composition version, when it is not approved;
    - the room's restyle looks.
  - Both panes already approve and unapprove the version they show (`workspace-pane-approval`). That control stays at the top of the pane, above the 3D view.
- **The room pane follows a composition build.** Progress is also polled while the room's latest composition version is queued or running. "Approve version N" therefore appears without a reload once the build succeeds.
- **Refusals stay as they are.** The service's reasons are already plain sentences, for example "Wohnen version 2 places listening-wall, which is not approved; approve those piece versions first". The pane shows them next to the control and never shows a status code or an internal code.
- **Unchanged:**
  - the Pieces page and the Measured Rooms page keep their own approval controls;
  - the backend approval routes and their refusals;
  - the Tools, Decisions so far, Brief and Project flyouts. `studio-navigation-tidy` removes Tools.

Ladder: none of the three steps. This is Studio UI only, with no schema, generator or Blender change. Agents touched: none; no model sees any of this. The **render guard** and the **bpy allow-list** are **not affected**. No render is started.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-ui`:
  - the chat pane header's Piece and Room icons open panes, not flyouts;
  - the piece and room panes carry approval, delete, looks, the version-limit notice and open requests, and follow a composition build;
  - the Project-flyout inspection requirement is removed.

## Impact

- `frontend/src/routes/Conversation.tsx`:
  - drop `PiecePanel`, `RoomPanel` and `RoomSection` as flyout content;
  - add the pane-opening rail entries;
  - move delete, looks, version-limit and open-request blocks into `PiecePane` and `RoomPane`;
  - add room-build polling to the `progress` query.
- `frontend/src/components/chat/Rail.tsx`: a panel entry may be an action that opens no flyout (`onSelect`). It keeps its icon, label, tooltip and keyboard focus.
- `frontend/src/components/ApprovalRow.tsx`: unchanged; reused by both panes.
- Tests: `frontend/src/routes/Conversation.test.tsx` and `frontend/src/components/chat/Rail.test.tsx` (Vitest). No backend change, so no new pytest.
- Spec drift noted in design.md: `split-project-panel` introduced the Piece and Room flyouts but was never synced into `openspec/specs/studio-ui`. This change writes the resulting behaviour into the main spec.
- Order: apply before `studio-navigation-tidy`, which edits the same header requirement.
