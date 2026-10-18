## Context

See proposal.md (Why). The current state the approach builds on:

- **`house_file.delete_version`** already removes everything a version owns:
  - reviews and their items, render runs and their feedback, verdicts, and pricings with their entries;
  - the notices' references to it, and its record.

  It moves the folder aside before the commit and discards it after. On the last version it deletes the `Piece` row, the `ThreadPiece` rows, and unbinds `Thread.package_id`. `_version_refusal` refuses approved, placed (`compositions.pieces_in_use`), building and rendering versions.
- **Deleting a conversation** lives in `api/chat.py` (`delete_thread`). Under `_running_lock` it refuses with 409 while the thread is in `_running`. It then calls `chat.forget` (checkpointer) and `house_file.delete_thread` (the index row; uploads and tool settings cascade), and removes `<upload_root>/<thread_id>`.
- **Version numbers** come from `storage.next_version`, the highest existing version or `.last_version` in the package folder. Removing the package folder frees the id, which then starts again at 1. This already happens when a last version is deleted.
- **The Foreman's fixed replies** (`PIECE_HAS_CONVERSATION`, `WHICH_PIECE`, `ROOM_QUESTION`) are chosen in the router from state the context node computes. `_attached(engine, messages)` already says whether the owner's latest message carries a design file.
- **On the Pieces page,** the piece dialog in `routes/Pieces.tsx` shows `DeleteVersion` for the shown version. `DeleteVersion` asks in place and shows a refusal with `FieldError`.

## Goals / Non-Goals

**Goals:**
- One owner action removes a piece with all its versions and conversations, or removes nothing.
- The confirmation states exactly what goes, read from the service, not guessed by the page.
- A design file that clashes with an existing piece is named on the turn it arrives, by code.

**Non-Goals:**
- Deleting pieces through an agent tool.
- An undo or trash.
- Cascading into compositions. A placed piece refuses, as a placed version does.
- Changing how a piece name in a message binds a conversation (the substring match seen on 2026-10-17). That is a separate fix.
- Matching a design to a piece by its contents.

## Decisions

1. **Reuse the version clean-up, not a second copy.** Split `delete_version`'s row-removal block into `_remove_version_rows(session, package_id, version)`. `delete_version` keeps calling it with its refusal unchanged. `delete_piece` calls it for every recorded version, then deletes the `ThreadPiece` rows and the `Piece` row. The package folder is moved aside as a whole (`storage.move_package_aside` / `discard_package` / `move_package_back`, beside the version equivalents) and discarded after the commit. Folder removal, `.last_version` included, frees the id.

2. **`piece_deletion(session, root, package_id)`** returns:
   - `versions`;
   - `approved`: version numbers with a `priced` flag from `CutListPricing`;
   - `conversations`: ids from `Thread.package_id` and `ThreadPiece`, deduplicated;
   - `refusal`: the first reason, or `None`.

   Refusal order: a placement in any composition (named with its version), then any version building, then any render queued or running. These are `_version_refusal`'s placed, building and rendering checks run per version, skipping the approval check. The GET route returns this as JSON. The DELETE route recomputes it, so a stale page cannot bypass a refusal.

3. **Conversations are deleted through the conversation delete's own path.** Factor the body of `api/chat.py`'s `delete_thread` into `delete_conversations(request, thread_ids)`. It runs under `_running_lock` and:
   - refuses with 409 if any id is in `_running`;
   - forgets each thread's memory (a failure gives 503 with `MEMORY_DOWN`, and nothing is deleted);
   - returns, so the caller removes the index rows in its own transaction and the upload folders after the commit.

   The piece route does this in one sequence:
   1. hold the lock and check refusals;
   2. forget the memory of every conversation;
   3. in one transaction, remove the version rows, the threads' index rows and the piece row;
   4. after the commit, remove the package folder and the upload folders.

   Forgetting memory first matches the conversation delete. If the database step fails after memory was forgotten, the conversations remain listed but empty, the same failure mode as the conversation delete today. This is noted in Risks.

4. **Routes.** `GET /packages/{package_id}/deletion` → 200 with the summary, or 404. `DELETE /packages/{package_id}` → 204, 404, 409 (`piece_in_use` with the reason, or `turn_running`), or 503 (memory). Both sit behind the owner gate like the other package routes.

5. **The design-file conflict check** runs in the Foreman's context node when the latest owner message carries a design file and the thread has no `package_id`. For the newest design upload of that message it reads:
   - the original file name's stem;
   - the design's `name`: `build.name` for a `package_import` wrapper, or `name` for a bare `custom_build`.

   The file is read through the uploads module, never sent to a model. A piece matches when:
   - the stem equals its id;
   - `storage.apartment_slug(name)` equals its id; or
   - `name.casefold()` equals the piece name's casefold.

   The first match by house-file order wins. The state gains `design_matches_piece: {package_id, name, file, has_conversation}`. The router places the `DESIGN_MATCHES_PIECE` reply before `PIECE_HAS_CONVERSATION` and the room question, and ends the turn. The text is fixed, with the second sentence chosen by `has_conversation`:

   > "The attached design `<file>` matches your piece <name> (`<id>`). To update that piece, attach the file in its conversation (Pieces page → <name>) and it becomes the next version. To start over, delete <name> on the Pieces page, then attach the file again. To keep both, change the design's name and attach it again."

   Without a conversation, the update route reads "name <id> here and attach the file again".

6. **The frontend.** `DeletePiece` mirrors `DeleteVersion`. Pressing it fetches the summary with TanStack Query and renders the lines in the studio-ui requirement. "Yes" is only offered without a refusal. On success it invalidates the pieces, threads and composition queries and closes the dialog. It sits in the piece dialog below the version controls in `routes/Pieces.tsx`, and `api.ts` gains `pieceDeletion` and `deletePiece`.

## Risks / Trade-offs

- **[Memory forgotten, then the database step fails]** → the conversations stay listed but empty. This is the same failure the conversation delete accepts today. It is logged, and the owner can delete them again.
- **[A matching name catches a design the owner meant as new]** → the reply offers "change the design's name" as an explicit way on. Nothing is imported or lost.
- **[Approved pricings are deleted]** → the owner chose this. The confirmation names each approved version and whether it was priced before "Yes".
- **[Concurrent build or turn starting during the delete]** → refusals are recomputed inside the lock for turns. Builds are checked from the status files just before the commit, the same as the version delete.

## Migration Plan

None. No schema change. Rollback is removing the two routes, the button and the fixed reply.
