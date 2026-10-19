## Context

A measured room is one `rooms` row: name, corners, height, wall thickness, openings, notes and an optional apartment. Its layout is a room-scope composition: `compositions` plus one `composition_versions` row per version, with each version's document in `input.json` under `docs/renders/compositions/<slug>/v<n>/`. `compositions.propose` validates a document against the house file, the library, the approved piece versions and the design rules. `compositions.create_version` writes the folder, records the version and starts the headless build. `house_file.upsert_room` replaces an existing room of the same name, so a duplicate must check the name itself. Pieces are duplicated by `app/packages/duplicate.py` with a check-then-create split (`plan`, then `create`). This change copies that shape.

## Goals / Non-Goals

**Goals:**
- One service is used by the route. Every refusal is raised by the check step, before anything is written.
- The copied layout passes through `compositions.propose`, so it meets exactly the rules any new composition meets.

**Non-Goals:**
- No chat tool and no Foreman change (owner's choice, 2026-10-19).
- No copying of apartment compositions. Only the room's own room-scope composition is a layout source.
- No renaming or moving a room, and no editing of the copy's measurements here (still done through Intake).

## Decisions

1. **`plan` and `create` in a new `app/rooms_duplicate.py`.** `plan(session, root, source, name, version)` returns a frozen `Plan` (`source`, `name`, `room` fields, `version`, `document`) or raises `RoomDuplicateRefused(code, message)` with the codes `not_found`, `invalid_name`, `name_taken`, `folder_in_use` and `layout_refused`. `create(session, root, plan, start)` writes the room with `upsert_room` (no `apartment_id`), and when a layout was chosen calls `compositions.create_version`, which commits. A shell-only copy commits itself. *Alternative:* add it to `house_file.py`. That module already holds many writers, and the duplicate needs `compositions`, which imports `house_file`. A separate module avoids the cycle, as `app/packages/duplicate.py` does.
2. **Name check by casefold over `rooms(session)`.** This mirrors `duplicate.name_taken`. `upsert_room` would otherwise overwrite the room silently.
3. **The layout is re-proposed against the copy.** The chosen version's `input.json` items and floor are passed to `compositions.propose` with `room=<new name>`, before the room exists. `propose` reads the room from the house file, so `plan` first adds the new room in the session with `upsert_room` and **flushes without committing**. If `propose` refuses, the session is rolled back, so nothing is written. *Alternative:* copy the folder as is. That skips the approval and rule checks the spec requires, and the document's `scope` and `resolved` block name the old room.
4. **The change line is set after `propose`.** `create_version` records `proposal.changes`. The plan replaces them with `["duplicated from <room> v<n>"]`, and `proposal.latest` is `None` for a new composition, so no "compared with" line appears.
5. **Slug collision is checked up front.** `storage.composition_slug("room", name)` is computed in `plan`. A slug already used by another composition, or a folder on disk, is refused as `folder_in_use` before any write, instead of failing inside `record_composition`.
6. **Route.** `POST /rooms/{name}/duplicate` with the body `{name: str, version: int | null}`. It answers 201 with `{room, composition: {slug, version} | null}`, 404 for an unknown source, and 409 for `name_taken` / `folder_in_use` / `layout_refused`. A layout copy is gated by `require_generation`, as package builds are. The build is started as a FastAPI background task calling `runner.run_build(..., record="room")`, following `packages._start_build`.
7. **Frontend.** `components/DuplicateRoom.tsx` is modelled on `DuplicatePiece.tsx`: in-place form, name prefilled "<name> (copy)", a select of `room.composition.versions` newest first plus "No layout". On success it invalidates `rooms` and `compositions`. It sits in the room dialog next to the delete control. A room in an apartment can be duplicated even though it cannot be deleted.

## Risks / Trade-offs

- [A copied layout can be refused for a reason the owner did not cause, such as a piece unapproved after the layout was made, or a design rule that changed since] → The refusal names the item and the reason. The owner can pick another version or "No layout".
- [Free-placed items (x, y) depend on the corner frame] → The corners are copied unchanged, including an apartment room's plan frame, so free placements stay where they were.
- [A building copy holds the Blender semaphore] → It is the same single headless build as any composition version. No render starts.
