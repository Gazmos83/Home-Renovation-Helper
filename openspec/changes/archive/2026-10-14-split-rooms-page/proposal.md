## Why

The Rooms page holds three unrelated lists on one long page: measured rooms, composition cards, and the model library with its upload form. A room's composition sits in a separate card away from the room it belongs to, and the library of bought models has nothing to do with measured rooms. The owner asked (2026-10-14) to split the page into "Measured Rooms" and "Model Library", laid out like the Pieces page.

## What Changes

- The Rooms page becomes the **Measured Rooms** page at `/rooms`, laid out like the Pieces page: a heading row, a one-line intro, then one card per measured room.
- Each room card holds that room's composition (version dropdown, approve/unapprove, delete version, items, picture, viewer link, variants, 3D view), instead of a separate composition card. A room without a composition says so and how to get one.
- Apartment compositions (and any room composition whose room is not in the house file) keep a card of their own below the room cards.
- The model library moves to a new **Model Library** page at `/models`, laid out the same way: heading row, intro, one card per model, and the upload form.
- The Studio navigation shows "Measured Rooms" and "Model Library" after "Pieces" in place of "Rooms".
- Not changed: every API route, the delete-room warning, approval and delete-version flows, the 3D view, the library's check polling. No behaviour of a control changes, only where it is shown.

Ladder step and agents: none — Studio UI only; no agent, prompt, tool or generator is touched. The render guard and the `bpy` allow-list are not affected.

## Capabilities

### New Capabilities

### Modified Capabilities
- `studio-ui`: the Rooms page requirement is replaced by a Measured Rooms page (rooms with their compositions inside) and a Model Library page, plus the two navigation entries.

## Impact

Frontend only: `frontend/src/routes/Rooms.tsx` (split), a new `frontend/src/routes/ModelLibrary.tsx`, `frontend/src/App.tsx` (nav link and route), `frontend/src/routes/Rooms.test.tsx` (library tests move to `ModelLibrary.test.tsx`; card lookups follow the new nesting). No backend, schema, migration or API change.
