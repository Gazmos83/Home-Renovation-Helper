## 1. Storage and limit

- [x] 1.1 `storage.next_version` honours a `.last_version` high-water file, and `storage.remove_version` moves a folder aside and removes it. Verify with unit tests: deleting the highest version then calling `next_version` returns the old highest plus one, and the dot-files are not listed as versions.
- [x] 1.2 Add `MAX_VERSIONS = 15` and `VersionLimitReached` in `packages/service.create_version`, and map it to 409 with the plain-words message in `api/packages.py`. Verify that the 16th version through the route is refused and that no folder is written.

## 2. Deleting a version

- [x] 2.1 Add `house_file.delete_version`, with these refusals: approved, placed in a composition (naming it), build or render queued or running, and missing. Verify each refusal with a unit test that also checks nothing changed.
- [x] 2.2 Have `delete_version` remove the reviews and items, render runs and feedback, pricings and entries, and the version row. It clears matching notices' piece and version. On the last version it deletes the piece and clears `threads.package_id` and `thread_pieces`, then commits and removes the folder, or restores the folder on failure. Verify with unit tests for the records, the notice, the last-version case and a forced folder failure.
- [x] 2.3 Add a `DELETE /packages/{id}/versions/{n}` owner route that returns 204, or 409 or 404 with the reason. Verify with API tests: an unauthenticated call is refused, and a numbering test shows a revision after deleting the highest version gets a new number.

## 3. Designer

- [x] 3.1 Have `revise_package.preview` and `rebuild_preview` refuse at 15 versions before the confirmation, and add "This will be version <n> of 15 the piece can hold." when n is 13 to 15. Verify with `test_revise.py` cases for 15 (refused, no confirmation), 12 (heads-up for 13) and 4 (no line).
- [x] 3.2 Have `designer.md` relay the limit refusal and never offer to delete a version itself. Verify with `test_instructions.py`.

## 4. Build notices

- [x] 4.1 Add migration `0017_thread_notice_kind`: `kind` defaults to `render` with a check constraint, and `tier` becomes nullable. Update the model and `house_file.add_notice`. Verify that `alembic upgrade head` and `downgrade -1` both run, and that existing notice tests pass.
- [x] 4.2 Add `notices.post_build` and the build text written by code. Attach a done-callback in `create_piece`, `revise_package` (including rebuild) and `blender_build`. Verify with unit tests: a succeeded build posts, a failed build posts with no error text, no thread posts nothing, a deleted thread posts nothing, and a posting failure is logged.
- [x] 4.3 Have the thread history API return `kind` for every notice, and confirm that no model call contains a build notice. Verify with `test_chat` history and "not sent to the model" tests.

## 5. Studio

- [x] 5.1 Add an `api.deleteVersion` client and a shared `DeleteVersion` component with an in-place "Are you sure?" (Yes and Cancel, and whole-piece wording on the last version). Verify with Vitest for confirm, cancel and the shown refusal.
- [x] 5.2 On the Pieces page, add delete for the shown version, hidden when approved, and refresh versions or drop the piece afterwards. Verify with `Pieces.test.tsx`.
- [x] 5.3 In the Project panel, remove "version N" from the header line, add delete for the latest unapproved version, show "N of 15 versions" from 13, and close the inspector when it shows the deleted version. Verify with `Conversation.test.tsx`.
- [x] 5.4 Make the inspector heading beside the chat show the piece name, falling back to the id, without the version. Verify with `Conversation.test.tsx`.
- [x] 5.5 Have `Notice` show "Inspect version N" for a succeeded build notice and no button for a failed or unlinked one, and refresh history when a followed build ends. Verify with Vitest.
- [x] 5.6 Add a `ModuleLabels` overlay in Exploded mode, showing name and W × H × D in mm, moving with the slider, following the `dimensions` switch, and showing nothing when `spec.modules` is absent. Verify with Vitest on the label text and the placement maths in `lib/inspector.ts`.

## 6. Checks

- [x] 6.1 Run `uv run ruff check .`, `uv run pytest -m "not slow"` (one process), `pnpm lint`, `pnpm test` and `pnpm build`, and record that all are green.
- [x] 6.2 Run a browser check of the Pieces page (delete and cancel), the Project panel (header and delete), a build notice's Inspect button, and Exploded labels on a built version. Use the existing blockout only; no render is needed (no tier). Record the result here.
- [x] 6.3 Owner check in the app: delete an old version of the listening wall, confirm the title has no version, and inspect a new build from its notice.
