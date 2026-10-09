## Context

See proposal.md, Why. The relevant parts of the system today:

- **Version numbering.** A version is a folder `docs/renders/<id>/v<N>/`. `storage.next_version` returns the highest existing folder number plus one, so deleting the highest folder would reuse its number.
- **Records.** `piece_versions` rows cascade from `pieces`.
  - `reviews` (with `review_items`), `render_runs` (with `render_feedback`) and `cut_list_pricings` (with its entries) key on `(package_id, version)` without a foreign key.
  - `thread_notices` carry an optional `package_id` and `version`.
  - `threads.package_id` and `thread_pieces` name a piece without a foreign key.
- **Version creation.** Every new version goes through `packages/service.create_version`:
  - the package routes;
  - `create_piece`;
  - `revise_package`, including the rebuild.
  `blender_build` re-queues an existing folder.
- **Builds run in the background.** `ToolDeps.start_build` schedules `runner.run_build` on the app loop and returns a future. Today nothing posts to the chat when the build ends. Only renders post notices (`agent/notices.py`, `thread_notices`, whose `tier` is required).
- **Inspector.** `spec.json` already has `modules[id] = {x, y, z, w, h, d, shelves}` and `module_names`. `lib/inspector.ts` `customBuildExplode` turns them into per-module offsets. `DimensionOverlay` draws `overall` and is hidden when exploded.
- **No dialog component** exists under `components/ui`. Existing destructive actions, such as deleting a conversation, use inline controls.

## Goals / Non-Goals

**Goals:**
- Delete one version safely, with all of its files and records.
- A hard limit of 15 versions per piece, enforced in code.
- A build-ended notice that carries the Inspect button.
- Module size labels in the exploded view.

**Non-Goals:**
- Restoring a deleted version: there is no trash.
- Deleting a version through an agent tool.
- Deleting several versions at once.
- Changing render notices.
- Per-part dimensions in the exploded view.

## Decisions

1. **Version numbers stay unique through a high-water mark file.**
   - **What:** on a delete, the service writes `docs/renders/<id>/.last_version` holding the highest number the package has had. `storage.next_version` returns `max(highest existing folder, .last_version) + 1`.
   - **Why:** this keeps storage independent of the database. Folder-only packages created through the routes work the same way.
   - **Alternative:** a `pieces.last_version` column. Rejected because `next_version` has no session, and folder-only packages have no `pieces` row.
   - **Hidden from listings:** the dot-file is ignored by `_version_numbers`, which only matches `v<N>`.
2. **One delete function owns the order.**
   - **What:** `house_file.delete_version(session, root, package_id, version)` checks every refusal first: approved, placed in a composition, building or rendering, missing. In one transaction it then:
     - deletes the rows: reviews and items, render runs and feedback, pricings and entries, then the version row;
     - clears `package_id` and `version` on matching notices;
     - when no version is left, deletes the piece and clears `threads.package_id` and `thread_pieces`.
     
     It then moves the folder to a sibling `.deleting-v<N>` and flushes. On commit it removes that folder; if the transaction fails, it moves the folder back.
   - **Why:** this matches the spec's rule that the records stay when the folder cannot be removed.
   - **Alternative:** delete the folder first. Rejected because a database failure would leave rows without a folder.
3. **Composition check by reading documents.**
   - **What:** composition version documents name `{package_id, version}` per item. `compositions.py` already reads them for model-library use. A small `pieces_in_use(package_id, version)` helper scans them in the same way.
   - **Why:** there are few compositions, so a scan is cheap. It also avoids a join table.
4. **"Running" means status or render run.**
   - **What:** the build is running when the version's status file reads `queued` or `running`. A render is running when a `render_runs` row for the version has outcome `queued` or `running`.
   - **Why:** this check also keeps the render guard's semaphore holders safe.
5. **The limit lives in `service.create_version`.**
   - **What:** `MAX_VERSIONS = 15`. `create_version` raises `VersionLimitReached` when `len(storage.versions(...)) >= 15`.
     - The route maps it to 409.
     - `revise_package.preview` and `rebuild_preview` call a shared `version_limit_refusal(deps, package_id)` before building the `Confirmation`. The owner is never asked to confirm something that will be refused.
     - The heads-up line is added in the same place when the new count would be 13, 14 or 15.
   - **Why:** one constant guards every path. The preview check is a convenience, and the raise in `create_version` is the guarantee.
6. **Build notices share `thread_notices`.**
   - **What:** a migration adds `kind` (`render` or `build`, default `render`, check constraint) and makes `tier` nullable. `notices.post_build(deps, thread_id, package_id, version, outcome)` builds the text in code, like `notice_text`.
     - Tools that start a build attach `future.add_done_callback` to post it: `create_piece`, `revise_package` (including rebuild) and `blender_build`.
     - The callback reads the status file for the outcome.
     - The routes pass no thread, so they post nothing.
   - **Why:** the history API and the frontend `Notice` already place notices among the messages. The frontend switches on `kind`: a build notice gets "Inspect version N" through the same `inspect()` as Review.
   - **Alternative:** a separate table. Rejected as duplication.
   - **Following without a reload:** the Project panel already refetches while a build is queued or running. Thread history is invalidated when the build status leaves `running`, as it is for renders.
7. **Inline "Are you sure?"**
   - **What:** a small `DeleteVersion` component shows the button, then the question with "Yes, delete version N" and "Cancel", in place. It is shared by the Pieces page and the Project panel.
   - **Why:** no new UI dependency, and it is easy to test with Vitest.
   - **Alternative:** `window.confirm`. Rejected because it is unstyled and awkward to test.
8. **Module labels are a sibling overlay.**
   - **What:** `ModuleLabels` takes `spec.modules`, `module_names`, the offsets and the explode amount. It places a drei `Html` label at each module's centre plus its offset, multiplied by the explode amount. The conversion from millimetres to scene units matches `PieceModel`.
   - **Why:** this reuses the `DimensionOverlay` styling, and like it uses page text, not 3D text, so no font is fetched.
   - **When it shows:** only when `mode === "exploded"` and the `dimensions` layer is on.
9. **Titles.**
   - **Project panel:** drop `version {latest_version}` from the header line.
   - **Inspector beside the chat:** the heading reads `spec.json` `name` through the inspector's existing spec query and falls back to the id. The `aside` heading moves into `InspectorView`'s compact header, or receives the name through a callback. The simpler of the two is chosen at implementation; this does not change behaviour.

## Risks / Trade-offs

- **[A deleted version is gone for good]** → Mitigation: the "Are you sure?" says it cannot be undone. Approved versions and versions placed in a composition are protected, and the design JSON can be downloaded first.
- **[A failure between the folder move and the commit leaves a `.deleting-v<N>` folder]** → Mitigation: the move is undone on rollback, and leftover `.deleting-*` folders are ignored by listings. Startup could sweep them; that is deferred.
- **[A build notice for a build that ends after a server restart is lost]** → Mitigation: this is accepted, the same as render notices. The Project panel still shows the state.
- **[An old checkpointed message still mentions a deleted version]** → Mitigation: this is accepted. The Designer reads the live version list from the house file slice, so it will not revise a missing version.

## Migration Plan

- One Alembic migration, `0017_thread_notice_kind`:
  - adds `kind` with server default `render` and a check constraint;
  - makes `tier` nullable.
  
  Downgrade deletes build notices, restores `NOT NULL` and drops `kind`.
- There is no data migration. Existing pieces above 15 versions are not trimmed. They only refuse new versions until the owner deletes down below 15.
