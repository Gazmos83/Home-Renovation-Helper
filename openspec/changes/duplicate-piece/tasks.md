## 1. Service

- [x] 1.1 Add `backend/app/packages/duplicate.py` with `duplicate(...)`, the refusal checks and the default-id helper (slug, then `-2`, `-3`…). Per design §1–§4: copy `input.json` and the frozen hardware inputs, replace only the name, record the piece with the source's room and brief, record v1 with the change line, and create a bound thread. No render, so **no tier**. Verify with `backend/tests/test_duplicate_piece.py` covering:
  - "Duplicate the latest version";
  - "Duplicate an earlier version";
  - "Approval is not copied";
  - "Id taken";
  - "Name already used";
  - "Design no longer valid";
  - a source with no frozen inputs;
  - the source's files and records unchanged.

## 2. Route

- [x] 2.1 Add `POST /packages/{package_id}/duplicate` to `backend/app/api/packages.py`, owner-gated and using `_start_build`. It returns 202 with `thread_id`. Verify with tests in `backend/tests/test_packages_api.py` for:
  - 202 with the build queued and the thread bound;
  - 404 for an unknown source or version;
  - 409 `package_exists` and `name_taken`;
  - 422 naming the field;
  - 503 without Blender;
  - 401 when signed out.

## 3. Designer tool

- [x] 3.1 Add plugin `backend/plugins/duplicate_piece/` (`manifest.yaml`: role designer, enabled by default, toggleable; `tool.py` with preview and run on the shared service, the build followed into the new thread). Add `"duplicate_piece": "The piece was not duplicated."` to `DECLINED` in `foreman.py`. Verify with `backend/tests/test_duplicate_piece_tool.py` for:
  - "Duplicate in the piece's own conversation" (this conversation's binding unchanged; the reply links the new conversation);
  - "Owner says no";
  - "Unknown source";
  - the manifest loads at startup.
- [x] 3.2 Add a short `duplicate_piece` paragraph to `backend/app/agent/instructions/designer.md`: when to use it, ask for a name when none is given, never retype the design. Verify that the existing instruction-loading tests pass.

## 4. "Keep both"

- [x] 4.1 In `backend/plugins/design_import/tool.py`, add the optional `name` to `ImportDesignArgs`. It replaces the design's name after `parse_import` and is refused when it equals an existing piece's name. Verify with tests in `backend/tests/test_import_design.py` for "New name still matches", a renamed import created under the new name, and imports without `name` unchanged.
- [x] 4.2 In `backend/app/agent/foreman.py`, change the third way of `DESIGN_MATCHES_PIECE` to the "keep both" wording. Detect "keep both" / "beide behalten" after that reply in code, and route to the Designer with `handoff_design` and the keep-both note (design §7). Verify with tests in `backend/tests/test_conversation_scope.py` for:
  - "Keep both with a new name" (Designer turn, note carries the upload id and the owner's words);
  - "Keep both without a name";
  - the updated reply text in "File named like an existing piece";
  - an unrelated reply after the fixed answer still routes as before.

## 5. Frontend

- [x] 5.1 Add `api.duplicatePiece` to `frontend/src/lib/api.ts`. Add a `DuplicatePiece` component (version dropdown with the latest chosen, name prefilled "<name> (copy)", id prefilled from the name and editable, Duplicate and Cancel). Wire it beside `DeletePiece` in `frontend/src/routes/Pieces.tsx`. On success, invalidate the pieces and threads queries and navigate to `/studio/workspace/<thread_id>`. Verify with `frontend/src/components/DuplicatePiece.test.tsx` for "Duplicate from the dialog", "Refusal shown" and "Cancel".

## 6. Checks

- [x] 6.1 Run `uv run ruff check .` and `uv run pytest -m "not slow"` in `backend/`, skipping the RunPod/offload test files and using a throwaway `TEST_DATABASE_URL` if another session holds the test database. Run `pnpm lint`, `pnpm test` and `pnpm build` in `frontend/`. All must pass.
  Result 2026-10-19, on the staged change alone: ruff clean; backend 2985 passed, 1 failed (`test_engineering_registry::test_migration_is_separate_from_legacy_chunks`, which already failed at HEAD: it expects head `0029`, while `0030` is committed); frontend lint, 560 tests and build pass.
- [x] 6.2 Browser pass, with **no render tier** (headless builds only):
  - duplicate Sideboard v1 from the Pieces page; the copy's conversation opens, its build succeeds, and Sideboard is unchanged;
  - in a new conversation, attach `sideboardo.json`, reply "keep both, call it Sideboard Hall", and confirm; the new piece is created;
  - in Sideboard's conversation, ask the Designer to duplicate it and confirm; the reply links the copy.
  Owner confirmed 2026-10-19: "duplication worked".
