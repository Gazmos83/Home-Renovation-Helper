## Context

`ProjectPanel` in `frontend/src/routes/Conversation.tsx` renders the piece block, the `RoomSection` and the progress steps from one `["progress", threadId]` query. The `Rail` takes a list of panels; each has an id, label and icon.

## Decisions

- Split `ProjectPanel` into `ProjectPanel` (steps, next, open review items), `PiecePanel` (piece block) and a thin `RoomPanel` around the existing `RoomSection`. All three read the same `progress` query, so the refresh while building or rendering is unchanged and shared.
- Add `piece` and `room` to the `Panel` icon union in `Rail.tsx` (lucide `Box` and `DoorOpen`).
- Only one flyout is open at a time already; the existing split view rule (opening a piece version closes the room view) is untouched.
- Loading and error states are shown by each panel, as today.
- Copy that points at "the Project panel" (render notices, build notices) is reworded to "the Piece panel" for a piece version and "the Room panel" for a composition.

- **Brief routes.** `GET /api/chat/threads/{id}/brief` returns the five fields (empty when none is confirmed) and `PUT` saves them, the thread taken from the path and the owner from the cookie. The body is a Pydantic model: purpose non-empty, height above 0, budget 0 or more, room one of the stored rooms; anything else is refused with a reason. The save writes the checkpoint's `brief` (`graph.update_state`), the bound piece's `brief`, and the style and budget preferences when the memory settings allow. It sets the thread's room as `confirm_room` does. A save while a turn is running is refused.
- **Brief panel.** A form with one labelled field per setting, a Save button, saved/refused text, and an empty state "No brief yet. Describe the piece in the chat, or fill this in." Saving with no brief confirmed counts as confirming it (the Brief step becomes done).

- **Agents' facts.** `brief_line` in `foreman.py` renders the set settings as `Brief: room: …; purpose: …; highest the piece may be: … mm; style: …; budget: … EUR`, appended to the facts line (from the checkpoint's brief, else the bound piece's). The facts already go to the Foreman's routing prompt and to every specialist's system prompt, so nothing else changes. Existing "confirmed brief: yes/no" stays as it was.
- **Room picture.** `room_progress` adds `approved_picture` (still, else screenshot, of the approved version), looked up directly because the approved version may be older than the five listed ones. The Room panel renders it after the approval controls, as the Piece panel does.

## Risks

- Existing tests look up the "Project" panel by name; they move to the new names. The tests change because the UI changed, not to hide a failure.
