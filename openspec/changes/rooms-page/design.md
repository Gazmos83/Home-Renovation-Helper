## Context

See proposal.md for the motivation. Current state:
- **`GET /rooms`** (`app/api/rooms.py`, from `conversation-projects`) returns room names only. Its one caller is the Pieces page room selector: `api.rooms()` in `src/lib/api.ts` is typed `string[]`, and `Pieces.tsx` maps each name to an option. `test_packages_api.py` asserts the name list.
- **Foreign keys.** `pieces.room_id`, `threads.room_id` and `rooms.apartment_id` are `ON DELETE SET NULL`. `composition_versions.composition_id` is `ON DELETE CASCADE`. A composition is tied to its room by scope and name only (`compositions.scope = 'room'`, `compositions.name = rooms.name`), not by a key.
- **Composition folders** live under `<render_root>/rooms/<slug>/v<N>/` (`storage.composition_dir`). A version folder holds `input.json`, `status.json` with the build `status` and one entry per render key under `renders`, the build files, renders and, after a detail pass, `detail/`.
- **Empty items.** `composition_contract.parse_composition` refuses an empty list ("items must be a non-empty list"). After that check nothing depends on items being present:
  - `place_items` keeps `scope_room` in `resolved.rooms` even when no item uses it;
  - `_composition.build_scene` builds the room shell, the lights and an empty `03_Items` collection, and computes the centre and radius from the room's corners;
  - `build_composition.py` writes a report with an empty `items` list, the screenshot and `model.blend`, and `verify_composition` checks only the three files;
  - `render_composition.py` aims its still and turntable cameras at the room's centre, not at the items.

  So the generator is expected to build an empty room unchanged. This is read from the code and not yet run; task 3.1 runs it.
- **Apartment scope with zero items** would resolve no rooms (`used` is empty and `scope_room` is `None`). `build_scene` would then fail on `max()` of an empty list. This is one reason the apartment scope keeps its minimum of one item.
- **Routing.** `foreman.load_house` sets `compose_ready` from an approved piece in the confirmed scope, or an existing composition there. Without either, a compose request in a thread with no piece and no brief goes to Intake. This is what the owner hit.

## Goals / Non-Goals

**Goals:**
- One read gives the Rooms page everything it shows, including the delete warning.
- A delete is all or nothing for the database, and leaves no stale version folder that a later room of the same name would continue numbering from.
- An empty room uses the existing build and render paths unchanged.

**Non-Goals:**
- Editing a room's measurements from the Rooms page. That stays with Intake.
- Deleting an apartment, or a room inside one (TODO(user)).
- Deleting a single composition or composition version on its own.
- Undo. The confirm dialog is the safeguard.
- Removing the room's name from stored briefs, chat history or notices. They are history; a brief naming a deleted room resolves to no room, as for an unknown name today.

## Decisions

1. **`GET /rooms` returns summaries; no separate preview route.** Each entry is:
   `{name, width_mm, depth_mm, corners, height_mm, openings, apartment, pieces: [{package_id, name}], conversations, composition: {slug, versions} | null}`.
   - Width and depth are the outline's bounding box. For an L-shaped room the page adds the corner count, so a 4 × 3 m L is not read as a rectangle.
   - The page builds the confirm dialog from the entry it already has.
   - *Alternative:* `GET /rooms/{name}/delete-preview`. Rejected: one more route and one more request, for data that is small and already needed on the page.
   - *Alternative:* keep `GET /rooms` as names and add `GET /rooms/details`. Rejected: two routes for one list. The one caller is changed in the same change: `api.rooms()` becomes `RoomSummary[]`, and `Pieces.tsx` maps `room.name`.

2. **`DELETE /rooms/{name}` in one transaction, folder moved aside first.**
   1. Refuse with 404 if the room is unknown, and with 409 if it has an apartment or its composition has a version whose build `status`, or any `renders` entry, is `queued` or `running`.
   2. Move `rooms/<slug>/` to a hidden sibling `rooms/.deleted-<slug>-<hex>/` with `os.replace`. It is the same file system, so the move is atomic.
   3. In one session: delete the composition row (its version rows cascade), then the room row (`pieces.room_id` and `threads.room_id` become NULL through their keys), then commit.
   4. If the commit fails, move the folder back and return the error.
   5. After the commit, remove the hidden folder with `shutil.rmtree(..., ignore_errors=True)`.
   - A leftover hidden folder is harmless: `list_compositions` matches slugs only, and `PACKAGE_ID_PATTERN` cannot start with a dot. It is never read as a version.
   - The route returns 204.
   - *Alternative:* commit first, then `rmtree`. Rejected: a failed removal would leave `v1…vN` under the slug, and a new room of the same name would start at `v<N+1>` beside stale files.
   - *Alternative:* a `room_id` key on `compositions` with `ON DELETE CASCADE`. Rejected: it needs a migration and backfill, and the folders still need code.

3. **Apartment rooms are refused, not guessed.** Deleting `Küche` from `Wohnung` would change the shell outline, the shared walls, and every apartment composition placing an item in `Küche`. The route answers 409 "`Küche` belongs to the apartment `Wohnung`; it cannot be deleted on its own yet." The page shows that text in place of the delete action. TODO(user): decide whether an apartment room is removed from the apartment (with a new shell version and the apartment's compositions refused or migrated), or whether only a whole apartment is deleted.

4. **Room scope may be empty; apartment scope may not.** `parse_composition` allows `len(items) == 0` only for `scope.room`. For an apartment it refuses with "an apartment composition needs at least one item". The `compose_room` summary for an empty room says "Room Hall: the room only, no items". `_changes` already lists every earlier item as removed, which covers the "last item removed" scenario.

5. **The generator is not changed unless the `--blender` run fails.** Task 3.1 adds an empty-room case to `tests/test_composition_blender.py`: a build, then a `draft` still. If it passes, there is no generator change (ladder step 1). If it fails, the smallest fix goes into `_composition.build_scene` or `build_composition.py` (ladder step 2). The run is repeated with `uv run pytest -m slow --blender -k composition` before any other task continues. No render runs outside the guard: the test passes the `draft` tier through the same argument parser the runner uses.

6. **`compose_ready` includes the confirmed room when the owner names it.** `compose_ready = bool(composed) or (the conversation's confirmed room is named in the owner's message) or <approved piece in scope>`. A confirmed apartment alone does not count, because an empty apartment cannot be composed. The Foreman's model choice still decides. This only stops the code from overriding a Designer choice with Intake for "compose Hall with no furniture".
   - *Changed during apply (2026-10-08):* the first version counted any confirmed room. That broke this change's own "No piece named" scenario ("revise it" with a confirmed room and no brief goes to Intake) and the "new wish goes to Intake whatever the model says" safety net, so the room must be named in the message.

7. **Rooms page layout.** A "Measured rooms" section goes above "Compositions" and "Model library".
   - The confirm dialog follows the inline pattern of `Conversations.tsx`: a confirm step inside the row, with Delete and Cancel buttons.
   - On success the page invalidates the `rooms`, `compositions` and `pieces` queries, so the Pieces page and its room selector update too.
   - The viewer link "Open the turntable viewer of <composition>" stays as `studio-layout` keeps it.

## Risks / Trade-offs

- [The Designer now keeps a turn it might not be ready for: a thread with a confirmed room, no brief, and a request for a new piece] → The Foreman's model still chooses Intake for a new piece. `create_piece` still needs a confirmed brief. The Designer's instruction line says an empty composition is for "the room with no furniture" only.
- [`test_foreman.py` asserts that "compose Wohnen with my furniture" goes to Intake while nothing is approved] → That is the behaviour this change reverses. The assertion is updated to the Designer, with a comment naming this change. The approved-piece half of the test stays.
- [A delete races with a build started a moment later] → It is a single owner, and the route checks build and render status inside the request. A build started after the folder was moved fails on its missing folder and reports it.
- [The composition is matched to the room by name] → The name is unique for rooms, and `uq_compositions_scope_name` makes it unique for room compositions. A room composition whose room was renamed outside this app is not removed; it stays listed as it is today.
- [The `GET /rooms` shape changes] → The one caller and its tests change in the same task (4.1, 4.2). The route is owner-only and has no other client.

## Migration Plan

- No database migration. No data is rewritten on deploy.
- Rollback: revert the code. Rooms deleted before the rollback stay deleted. Their pieces stay unassigned and can be attached again from the Pieces page.

## Open Questions

- TODO(user): how a room inside an apartment should be deleted (decision 3). Until it is answered the route refuses it, and nothing else in this change depends on the answer.
