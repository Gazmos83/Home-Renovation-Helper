## 1. House file and storage

- [x] 1.1 Extract `_remove_version_rows` from `house_file.delete_version` with no change in behaviour. Verify that the existing version-delete tests pass unchanged.
- [x] 1.2 Add `storage.move_package_aside`, `discard_package` and `move_package_back`, beside the version helpers. Verify with storage tests: a moved-aside package is not listed, moving it back restores it, and after discarding it `next_version` is 1.
- [x] 1.3 Add `house_file.piece_deletion` (versions, approved with priced, conversations, refusal) and `delete_piece` (all version rows, `ThreadPiece` and `Piece` rows, the given threads' index rows, and the package folder after commit). Verify with house-file tests for:
  - "Piece with an approved version deleted";
  - "What would go";
  - "Placed in a composition";
  - "Still building";
  - "Id reused";
  - engineering records and extension requests are kept.

## 2. Routes

- [x] 2.1 Factor the conversation delete in `backend/app/api/chat.py` into a helper used by `DELETE /threads/{id}` and by the piece delete, holding `_running_lock`. Verify that the existing conversation-delete tests pass unchanged.
- [x] 2.2 Add `GET /packages/{id}/deletion` and `DELETE /packages/{id}` to `backend/app/api/packages.py` (owner-gated). Verify with API tests for:
  - 204 and the piece and its conversation gone;
  - 409 `piece_in_use` naming the composition;
  - 409 `turn_running`;
  - 503 when memory is down, with nothing removed;
  - 404;
  - 401 for both routes.

## 3. Foreman

- [x] 3.1 In `backend/app/agent/foreman.py`, compute `design_matches_piece` in the context node (stem, `apartment_slug(name)`, or casefolded name; only when the thread has no piece). Add the `DESIGN_MATCHES_PIECE` fixed reply ahead of `PIECE_HAS_CONVERSATION` and the room question. Verify with foreman tests for:
  - "File named like an existing piece" (no specialist runs, no room question);
  - "Name inside the design matches";
  - "No match";
  - "Bound to the matching piece";
  - the no-conversation wording.

## 4. Frontend

- [x] 4.1 Add `api.pieceDeletion` and `api.deletePiece` to `frontend/src/lib/api.ts`, and a `DeletePiece` component. Wire it into the piece dialog in `frontend/src/routes/Pieces.tsx`. Verify with Vitest for:
  - the confirmation lines (approved and priced, conversations);
  - "Cancelled";
  - a refusal shown with no "Yes" button;
  - on success the dialog closes and the pieces and threads queries are invalidated.

## 5. Checks

- [x] 5.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` in `backend/`, skipping the RunPod/offload test files and using a throwaway `TEST_DATABASE_URL` if another session holds the test database. Run `pnpm lint`, `pnpm test` and `pnpm build` in `frontend/`. All must pass.
- [x] 5.2 Browser pass, with **no render tier**:
  - on the Pieces page, delete a throwaway imported piece that has an approved version and a conversation; the confirmation lists both, and afterwards the piece and its conversation are gone;
  - then attach a design named like another existing piece in a new conversation; the fixed reply appears and no interview starts.
