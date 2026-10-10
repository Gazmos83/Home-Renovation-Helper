## Context

See proposal.md for the why. Current state the approach builds on:

- Piece versions already have `approved_at`, owner routes `PUT`/`DELETE /packages/{id}/versions/{n}/approval`, and `DELETE /packages/{id}/versions/{n}` with "Are you sure?" in the Studio (`piece-first-workflow`, `version-cleanup-and-inspection`).
- `CompositionVersion` (`composition_versions`) holds `composition_id`, `version`, `revised_from`, `changes`, `created_at`. Latest migration: `0017_thread_notice_kind`.
- `compose_room` already refuses an unapproved piece at proposal time. Unapproving a placed piece is allowed today; the composition stays and reads "no longer approved".
- Composition version folders live under `docs/renders/rooms/<slug>/v<N>/`. `next_composition_version` is highest existing folder plus one, so deleting the highest would reuse its number.
- The Rooms page lists compositions with a newest-five version dropdown. The Project panel's "Selected room" section opens the 3D view; it has no approve or delete.

## Goals / Non-Goals

**Goals:**
- Approval as an owner act on a composition version, stored once, read wherever that version is shown.
- Delete one composition version safely, with its folder and row, without reusing numbers.
- Keep an approved room version's placed pieces approved, by refusing the unapprove that would break it, with the reason shown in the Studio.

**Non-Goals:**
- A 15-version cap on compositions.
- Deleting a measured room (already on the Rooms page).
- Changing `compose_room`'s argument schema or the render guard.
- Restoring a deleted version.

## Decisions

1. **Approval on the composition version row, one per composition by index.** Add `composition_versions.approved_at TIMESTAMPTZ NULL` and a partial unique index on `(composition_id) WHERE approved_at IS NOT NULL`. `house_file.approve_composition_version` clears the composition's other approval and sets this one; it also reads that version's document and refuses when a placed piece is not currently approved. `unapprove_composition_version` clears it. *Alternative:* `compositions.approved_version`. Rejected: piece approval lives on the version row, and the spec reads approval as a property of a version.

2. **Owner-gated routes on the composition router.** `PUT` and `DELETE /compositions/{slug}/versions/{n}/approval`, and `DELETE /compositions/{slug}/versions/{n}`. 404 for an unknown slug or version, 409 `not_built` when status is not `succeeded`, 409 `unapproved_pieces` when approving a version that still places an unapproved piece, 409 `version_in_use` for a refused delete. Listing, version views and `Progress.room` gain `approved_version` / `approved_at`. *Alternative:* a gated agent tool. Rejected: same as piece approval — the owner's acceptance stays off the model.

3. **Unapprove of a piece checks approved room placements.** `house_file.unapprove_version` takes the render root, finds composition versions that place that package/version, and refuses when any of those versions is currently approved, naming them. The piece route answers 409 `placed_in_approved_room`. Unapprove of a piece that is only in unapproved room versions stays as today. *Alternative:* silently mark "no longer approved" inside an approved room. Rejected: the owner asked to be told, and an approved room should not hold an unapproved piece.

4. **Delete a composition version like a piece version.** Refusals first: approved, building or rendering, missing. Move the folder aside (write `.last_version` so `next_composition_version` never reuses a number), delete the row, commit, then discard; on failure move the folder back. The last version also deletes the `compositions` row; the measured room is untouched. Busy state is read from that version's `status.json` (build and its `renders` map), matching `_composition_busy` per version. *Alternative:* also scan `render_runs`. Rejected: composition renders key `package_id` as the slug only in some paths; `status.json` is the source the runner already writes for both build and render.

5. **Studio.** The Rooms page's composition card shows Approve/Unapprove for the chosen succeeded version, and Delete (hidden while approved) with the existing in-place "Are you sure?" pattern. The Project panel's Selected room section mirrors the piece panel: latest vs approved, Approve latest, Unapprove, Delete latest. Version dropdown labels include "(approved)". Piece Unapprove already shows `FieldError` next to the button; the new 409 reason appears there.

## Risks / Trade-offs

- [The owner unapproves a room, then a piece, and expects the room to stay "approved looking"] → The panel shows "No version approved yet" as soon as the room is unapproved; composing again creates a new unapproved version.
- [Approving a room after a placed piece was unapproved] → 409 names the pieces; the owner approves those versions first (or composes them out).
- [Deleting the latest version while the 3D view is open] → the listing refreshes; the dropdown falls back to the new latest.

## Migration Plan

`0018_composition_approval`: add the nullable column and the partial unique index; every existing composition version reads unapproved. Downgrade drops the index and the column. No data backfill. Rollback of the code alone is safe: the column is ignored. The revision id is shorter than Alembic's 32-character `version_num`.

## Open Questions

None. Unapprove of a piece inside an approved room is refused (owner: inform when trying to unapprove).
