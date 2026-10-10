## Why

Piece versions can be approved, unapproved and deleted from the Studio. Room composition versions cannot: there is no approval mark, and no way to remove a version. The owner asked to treat a room version like a piece version, and to keep an approved room holding only currently approved pieces.

## What Changes

- **Approve and unapprove a room version.** The owner approves one built version of a composition from the Rooms page and the conversation's Project panel, and can unapprove it. At most one version per composition is approved. A new compose creates a new, unapproved version; approval never carries over. Approval is an owner act on owner-gated routes: no model tool can approve or unapprove.
- **An approved room holds only approved pieces.** Approving a room version is refused when any placed piece version is not currently approved, naming those pieces. Unapproving a piece version that is placed in an approved room version is refused, naming the room and version, until that room version is unapproved. Unapproving a piece that is only in unapproved room versions stays as today: the placement remains, marked "no longer approved". `compose_room` already refuses unapproved pieces at proposal time.
- **Delete a room version.** The Rooms page (the version shown) and the Project panel (the latest version) get a "Delete version N" control with "Are you sure?" first. Deleting removes that version's folder (model, screenshot, renders) and its house-file row. Refused, with the reason, when the version is approved, or still building or rendering. Deleting the last version of a composition removes the composition, not the measured room. Version numbers are never reused.
- Ladder: **step 1**. Touches the **Designer** only in that `compose_room` already refuses unapproved pieces (no tool-signature change). Approval and delete are Studio owner routes. The **render guard and the bpy allow-list are not affected**; nothing new renders.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `room-composition`: a composition version can be approved, unapproved and deleted; approving is refused when a placed piece is not approved.
- `house-file`: composition version records carry approval; deleting a version removes its row and folder; the last version removes the composition.
- `furniture-packages`: unapproving a piece version placed in an approved room version is refused until that room is unapproved.
- `studio-ui`: the Rooms page and the Project panel show room-version approval and delete.

## Impact

- Backend: `CompositionVersion.approved_at` and Alembic `0018_composition_approval`; `house_file` approve/unapprove/delete; `storage.next_composition_version` keeps a high-water mark; `PUT`/`DELETE /compositions/{slug}/versions/{n}/approval` and `DELETE /compositions/{slug}/versions/{n}`; `unapprove_version` of a piece checks approved room placements; composition listing, version views and thread progress report `approved_version` / `approved_at`.
- Frontend: `api.ts`; Rooms page composition card; Project panel room section; delete confirmation for a room version.
- Tests: house file, compositions API, packages unapprove, progress, Vitest for Rooms and Conversation, one browser check of approve/unapprove/delete.
- One migration, no new dependency, no change to `config/`.
