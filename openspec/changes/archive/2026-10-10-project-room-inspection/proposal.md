## Why

The conversation's Project panel opens a piece version beside the chat, but the room the conversation is about can only be seen in 3D on the Rooms page, away from the chat. The owner wants to look at the room while talking about it, the same way they already look at a piece.

## What Changes

- The thread progress read reports the conversation's confirmed room or apartment: its name, its scope, and, when its composition's latest version has `model.glb`, the composition's slug and the routes of its model and surface map.
- The Project panel shows a room section under the piece: a button that opens the room's 3D view, or a short note when there is no 3D view yet. Nothing is shown when the conversation has no confirmed room or apartment.
- The room's 3D view (the Rooms page's `RoomView`) opens beside the chat in the same split screen as the piece inspector, with a close control, and is part of the page's address (`?room=<slug>`) so a reload shows it again.
- One side pane at a time: opening the room view closes an open piece inspector, and opening a piece version closes the room view.
- Added after the owner's check (2026-10-09):
  - The Project panel's room section is headed "Selected room" above the room's name.
  - The room's 3D view, on the Rooms page and beside the chat, gets a "dimensions" switch that labels every unique wall with its length and each room's ceiling height (an apartment's rooms can differ; a wall two rooms share is labelled once).
  - A composition's versions are offered in a dropdown, on the Rooms page and beside the chat, listing the newest 5. Every version is still kept; nothing is deleted or refused.

Decided by the owner on 2026-10-09: the link opens the **conversation's** confirmed room (or apartment), not the active piece's assigned room; a room without a 3D view shows a short note rather than hiding the section; "up to 5 versions" means the dropdown lists the newest 5, with every version kept; the dimensions show every unique wall length and the ceiling height, which can differ per room.

Ladder step and agents: none. No agent, prompt, tool or ladder step changes; this is a read and a UI change. The render guard and the `bpy` allow-list are not affected; nothing is built or rendered.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `homeowner-chat`: the thread progress read also reports the conversation's room or apartment, its composition's 3D view routes and its newest 5 versions.
- `studio-ui`: the Project panel offers the room's 3D view under a "Selected room" heading, and the conversation view shows it beside the chat as a split screen, one side pane at a time, with a version dropdown and a dimensions switch; the Rooms page's composition card gets the same version dropdown and dimensions switch.
- `room-composition`: each composition version's wall lengths and ceiling heights can be read, derived from that version's stored document.

## Impact

- Backend: `backend/app/agent/progress.py` (or the progress route in `backend/app/api/chat.py`) reads `house_file.thread_scope` and `composition_by_scope`; `ProgressOut` gains a `room` field. Tests in the progress/chat API tests.
- Frontend: `frontend/src/lib/api.ts` (`Progress` type), `frontend/src/routes/Conversation.tsx` (`ProjectPanel`, the `?room=` parameter, the side pane). Tests in `Conversation.test.tsx`.
- Backend also: `backend/app/compositions.py` (wall and ceiling dimensions from a version's `input.json`), `backend/app/api/compositions.py` (`versions` on the listing; new `GET /compositions/{slug}/versions/{n}/dimensions`).
- Frontend also: `routes/Rooms.tsx` (version dropdown), `components/inspector/RoomView.tsx` and `InspectorCanvas.tsx` (dimensions switch and wall labels).
- No migration, no new dependency, one new read-only route.
