## 1. Render now

Revised 2026-10-18 (owner): "Render version N now" is for room versions. 1.1–1.3 were first built for pieces; 1.4–1.6 move it to rooms, remove the piece Renders tab and delete the piece renders.

- [x] 1.1 Add `GET /packages/{id}/versions/{n}/render-estimate` in `backend/app/api/renders.py`, reusing `_price_args`, `_with_target`, `quote` and `_require_built` and never authorising or queueing. Write tests for "Draft estimate read", "Estimate without a benchmark" and "Raw values refused", including that no status entry is written. Not run yet, see 4.3.
- [x] 1.2 Add `render_job` to `read_version` in `backend/app/api/packages.py`, from the status file's queued or running render entry. Write a test with a queued `draft` turntable status.
- [x] 1.3 In `frontend/src/lib/api.ts`, add `renderEstimate`, `startRender` and `VersionInfo.render_job`. In `RendersTab.tsx`, add "Render version N now" for a built version with no renders: the plain sentence with the estimate, Start and Cancel. Start requests a **`draft`** turntable. Show "Rendering version N… about …" while `render_job` is present, then select the new turntable. In `InspectorView.tsx`, poll while `render_job` is present. Write Vitest cases for "No renders yet", "Render now", "Cancel before starting" and "No benchmark yet". Verify with `pnpm test`.

- [x] 1.4 Remove the piece Renders tab from `InspectorView.tsx` (and `?tab=renders` opens the Model tab), the piece render-estimate route and `render_job` on the piece version, and the Review button of a piece render's notice. Verify with Vitest ("the piece inspector has no Renders tab", "a piece render notice is text only").
- [x] 1.5 Add the room routes in `backend/app/api/compositions.py` (estimate, draft-only start, renders list with `render_job`) and the room pane's "3D view" / "Renders" tabs with `RoomRendersTab` and "Render version N now". Verify with tests in `test_compositions_api.py` and Conversation tests for "No renders yet", "Render now", "Cancel before starting" and "No benchmark yet".
- [x] 1.6 Delete every existing piece render (render files under each piece version and its `status.json` render entries, and their `render_runs` / `render_feedback` rows) after a backup outside the repository. Done 2026-10-18: 9 runs and 2 ratings for `lamellen-kommode`, `murphy-bed` and `sideboard-1200`.

## 2. Blueprints

- [x] 2.1 Add the `blueprints` model to `backend/app/db/models.py` with an Alembic migration (unique `apartment_id` + `source_upload_id`, FK cascade). Verify with `uv run alembic upgrade head` on a throwaway database.
- [x] 2.2 Add a `keep_blueprints(session, upload_root, apartment, thread_id)` helper that copies the thread's PNG and JPEG uploads to `<upload_root>/blueprints/<id>.<ext>` and skips ones already kept. Call it in `run_plan` (`backend/plugins/intake/tool.py`) after `upsert_apartment`; a copy failure is logged and the plan stays. Write tests for "Plan confirmed", "Conversation deleted", "Plan declined" and "Plan read again".
- [x] 2.3 Add `GET /rooms/{name}/blueprints` in `backend/app/api/rooms.py` and `GET /blueprints/{id}` (attachment, original type, `nosniff`, 401 without a cookie, 404 when unknown). Write route tests.
- [x] 2.4 Show "Download blueprint <name>" links in `MeasuredRoom` in `frontend/src/routes/Rooms.tsx` via `api.roomBlueprints`, and none when the list is empty. Write Vitest cases in `Rooms.test.tsx` for "Blueprint downloaded" and "Room measured by hand".

## 3. Verdict note

- [x] 3.1 In `frontend/src/components/inspector/VersionVerdict.tsx`:
  - add the `editing` state and remove saving on blur;
  - guard saves with `give.isPending`;
  - show Save for either thumb while the note changed, and the saved note as text with "Saved" and Edit;
  - make Escape cancel an edit.

  Write Vitest cases for "Note on a thumbs up saved with Enter" (one request only), "Note edited", "Edit cancelled", "Note required" and "Blockout marked wrong in the inspector". Verify with `pnpm test` and `pnpm lint`.

## 4. Checks

- [x] 4.1 Browser pass of the room inspector's Renders tab, tier **`draft`**: on a built room version with no renders, press "Render version N now", read the estimate sentence, press Cancel, then Start. Watch the "rendering" line and the turntable appear selected.
- [x] 4.2 Browser pass with **no render tier**:
  - confirm a plan from an attached PNG in a new conversation, then download it from the Measured Rooms page;
  - delete that conversation and download it again;
  - in the inspector, save a thumbs-up note with Enter, see "Saved", then edit it and cancel with Escape.
- [x] 4.3 Run `uv run ruff check .` in `backend/` and `pnpm lint` in `frontend/` now. pytest is deferred to the batch check after the last change of the 2026-10-18 review batch (skip RunPod/offload tests, throwaway TEST_DATABASE_URL); the tests written above must pass there.
