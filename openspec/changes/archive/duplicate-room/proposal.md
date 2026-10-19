## Why

The owner wants to try a second arrangement or a variant of a measured room, such as Wohnen with a different layout, without measuring it again in a conversation. Today the only way to get a second room is to have Intake record the same numbers again under a new name, and its layout has to be composed from scratch. Pieces can already be duplicated (`duplicate-piece`, 2026-10-19). Rooms cannot.

## What Changes

- **Duplicate a room.** The owner makes a new room from an existing one and gives it a new name, prefilled as "<name> (copy)". The name must not be used by another room.
  - The copy takes the room's corners, ceiling height, wall thickness, openings and notes unchanged.
  - A room that belongs to an apartment is copied as a standalone room, outside any apartment. Its corners stay in the plan frame they were measured in.
- **One layout comes along.** When the room has a composition, the owner picks one of its versions (the latest is preselected) or "No layout". The chosen version becomes version 1 of the copy's composition, with the change line "duplicated from <room> v<n>", and its headless build starts at once. Its items, hidden flags, layers, lights, LED strips and floor finish are copied as they are.
  - The layout is checked against the copy exactly as a new composition is: every placement, opening and design rule. Only approved piece versions are allowed, so a layout holding a piece version that is no longer approved is refused by name, and nothing is created.
- **Not copied:** composition approvals, renders and variants, other layout versions, the pieces' room assignment and saved places, conversations, and blueprints. The original is never changed.
- **Rooms page.** The room dialog gains "Duplicate room", asked in place like "Delete room": a name field, the layout choice, and Duplicate / Cancel. A new owner route is added: `POST /rooms/{name}/duplicate`. There is no chat tool, by the owner's choice.

Ladder: step 1 only. The copy's layout is a composition version built headless by the existing generator. Agents touched: none. The **render guard** and the **bpy allow-list** are **not affected**. A duplicate starts only a headless build, never a render.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `house-file`: a new requirement that a measured room can be duplicated, covering what is copied, the layout version that comes along, and when a duplicate is refused.
- `studio-ui`: a new requirement for "Duplicate room" in the Rooms page's room dialog.

## Impact

- Backend: a new `app/rooms_duplicate.py` (plan and create, shared checks before any write), a new route in `app/api/rooms.py`, and a room-build starter for the route (the package route's `_start_build` pattern with `record="room"`).
- Frontend: a `DuplicateRoom` component beside `DuplicatePiece`, wired into the room dialog in `routes/Rooms.tsx`, and an `api.duplicateRoom` call.
- No migration: the copy uses the existing `rooms`, `compositions` and `composition_versions` tables.
- Tests: backend route and service tests, and Vitest tests for the dialog.
