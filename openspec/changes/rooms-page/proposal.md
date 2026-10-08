## Why

The owner asked for "a room composition with no furniture" and expected the room to show on the Rooms page. Intake recorded the measured room, but nothing more happened: a composition must hold at least one item, and the Rooms page lists only compositions and the model library. A measured room is invisible in the Studio, and a room measured by mistake cannot be removed. Owner decisions of 2026-10-08.

## What Changes

- **Measured rooms on the Rooms page.** A new first part lists every room of the house file: its name, its size, its ceiling height, its number of openings, the apartment it belongs to (if any), and the pieces in it. The compositions and the model library stay as they are.
- **`GET /rooms` grows from names to room summaries.** Each entry carries the fields above, plus what a delete would affect: the conversations that confirmed the room and the room's composition with its versions. The Pieces page room selector reads `name` from each entry. **BREAKING (API shape)** for the one caller, the Pieces page, which changes with it.
- **Delete a room, warn first.** Each room has a delete action. A confirm dialog names what happens:
  - its pieces become "No room";
  - the conversations that confirmed it lose their confirmed room;
  - its composition (scope room, same name) and every version of it are removed, rows and version folders.

  Nothing is deleted before the owner confirms. A new owner-gated route `DELETE /rooms/{name}` does it: 404 for an unknown room, 401 without the cookie, 409 while a build or render of the room's composition is queued or running.
- **A room inside an apartment is not deleted in this change.** Deleting it would change the apartment's shell and its compositions. The route refuses it with 409 naming the apartment, and the page shows why. TODO(user): how an apartment room should be deleted.
- **An empty room composition.** A room-scope composition may hold zero items. `compose_room` accepts an empty item list for a room, so a measured room with no furniture can be composed, built headless and shown on the Rooms page. An apartment scope still needs at least one item.
- **A compose request reaches the Designer once a room is confirmed.** Today a thread with no piece and no brief reaches the Designer for a composition only when an approved piece or a composition exists in its room. With an empty composition possible, a confirmed room is enough.
- Ladder: **step 1** (spec change and headless build). The composition generator already builds the room shell when the item list is empty; this is verified by the `--blender` suite, not assumed. If that run fails, the generator fix is a **step 2** generator extension inside this change, and the `--blender` suite is run again before anything else continues.
- Agents touched: the **Designer** (`compose_room` accepts an empty room) and the **Foreman** (routing of a compose request). Intake, the Builder, the Reviewer, Lighting & materials and the Researcher keep their tools. Deleting a room is a Studio action, not an agent tool.
- **Render guard: not affected.** An empty composition renders through the guard like any other: tier required (`draft`, `preview`, or `final` after the owner's "yes"), raw values refused, estimate stated. **bpy allow-list: not affected.** No live script, no new import.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `house-file`: a room can be deleted by the owner, with its effects on pieces, conversations and the room's composition. Added requirement only.
- `room-composition`: a room-scope composition may hold zero items, and its build is the room alone.
- `design-agents`: `compose_room` accepts an empty room; the Foreman lets a compose request reach the Designer once the conversation has a confirmed room.
- `studio-ui`: the Rooms page lists measured rooms with their details and pieces, and deletes a room after a confirm dialog; an empty composition is shown as the room only.

## Impact

- **Depends on** `conversation-projects` (implemented, not archived): it adds `GET /rooms`, `PUT /packages/{id}/room`, `threads.room_id` and `pieces.room_id` (both `ON DELETE SET NULL`). This change builds on them and must be archived after it. The `design-agents` routing delta starts from `conversation-projects`' version of that requirement.
- **Compatible with** `studio-layout`: the Rooms page keeps "Open the turntable viewer of <composition>".
- **Backend:**
  - `app/api/rooms.py`: room summaries on `GET /rooms`, and `DELETE /rooms/{name}`.
  - `app/agent/house_file.py`: room summary and room deletion.
  - `app/blender/storage.py`: remove a composition's folder safely.
  - `app/blender/composition_contract.py`: empty items allowed for a room scope.
  - `app/compositions.py`: the summary of an empty room.
  - `plugins/compose_room/tool.py`: argument description.
  - `app/agent/foreman.py`: `compose_ready`.
  - `app/agent/instructions/designer.md`: one line.
  - `app/blender/generators/build_composition.py` and `_composition.py`: unchanged unless the `--blender` run shows otherwise.
- **Frontend:** `src/lib/api.ts` (room summary type, delete call), `src/routes/Rooms.tsx`, `src/routes/Pieces.tsx` (reads `name`), and their tests.
- **Tests:** `test_packages_api.py` (the `GET /rooms` shape), `test_composition_contract.py`, `test_compose_room.py`, `test_foreman.py`, `test_house_file.py`, a new `test_rooms_api.py`, `test_composition_blender.py`, `Rooms.test.tsx`, `Pieces.test.tsx`.
- No migration, no new dependency, no change to `config/`.
