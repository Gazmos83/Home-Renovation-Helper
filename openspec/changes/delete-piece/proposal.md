## Why

A piece the owner no longer needs cannot be removed in one step. Today the only way is to delete its versions one by one, unapproving each approved version first. `listening-wall` would take ten deletes. The leftover piece also gets in the way.

On 2026-10-17 the owner attached `kommode-harmony.json` while a piece `kommode-harmony` already existed. Nothing said so. Intake started a new brief interview instead, and the conversation then got stuck on another piece. The owner wants a conflict like that named the moment the file is attached, and a piece they are done with deleted together with its conversations, because continuing those conversations only confuses.

## What Changes

- **Delete piece.** The piece dialog on the Pieces page gains "Delete piece", asked in place like "Delete version N". It uses a new owner route, `DELETE /packages/{package_id}`, and a read-only `GET /packages/{package_id}/deletion` that says what would go. One confirmation deletes:
  - every version of the piece, with its folder, renders, reviews, verdicts and pricings;
  - the piece record;
  - every conversation bound to the piece, with its memory, uploads and tool settings, exactly as deleting the conversation does.

  Approved versions do not block a piece delete. The confirmation names them and their pricings, and says how many conversations go with the piece. It is refused, naming the reason and changing nothing, while:
  - a room composition places one of its versions (named with the composition and its version);
  - a build or render of the piece is queued or running;
  - a turn is running in one of its conversations.

  The package id is then free again, so a new piece with that id starts at version 1. No agent tool deletes a piece.
- **A design file that matches an existing piece is named on the turn it is attached.** A design file matches when its file name, or the name inside it, gives an existing piece's id, or the name is that piece's name. If the conversation has no piece, the application answers that turn itself with a fixed reply, before any specialist or the room question runs. The reply names the piece and the three ways on:
  - import the file as that piece's next version (from its conversation, or by saying so here when it has none);
  - delete the piece on the Pieces page first, then attach the file again;
  - change the design's name to keep both.

  A conversation already bound to the matching piece imports as before.

Ladder: none of the three steps; this is house-file, API and UI work with no generator change. Agents touched: the **Foreman** (a new fixed reply decided by code); no specialist gains or loses a tool. The **render guard** and the **bpy allow-list** are **not affected**: deleting never renders, and a running render refuses the delete.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `furniture-packages`: a new requirement that a whole piece can be deleted, with its versions and conversations, and when that is refused.
- `studio-ui`: a new requirement for "Delete piece" in the piece dialog, with its confirmation.
- `design-import`: a new requirement that a design file matching an existing piece is answered with a fixed reply on the turn it is attached.

## Impact

- `backend/app/agent/house_file.py`:
  - `piece_deletion(session, root, package_id)`, which says what would go and why it may be refused;
  - `delete_piece(...)`, which reuses the per-version clean-up of `delete_version` without the approval refusal.
- `backend/app/api/packages.py`: `GET /packages/{id}/deletion` and `DELETE /packages/{id}`.
- `backend/app/api/chat.py`: conversation deletion factored into a helper both routes use, so a piece delete removes memory, index entry and uploads in the same order and under the same running-turn lock.
- `backend/app/agent/foreman.py`: a design-file conflict check in the context node and a `DESIGN_MATCHES_PIECE` fixed reply ahead of the room question.
- `frontend/src/components/DeletePiece.tsx` (new), `frontend/src/routes/Pieces.tsx`, `frontend/src/lib/api.ts`, with Vitest tests.
- Unchanged:
  - version delete and conversation delete behave as before;
  - engineering assessments and generator-extension requests keep their rows, as they do when a last version is deleted today;
  - the protection of approved versions against a single-version delete stays.
