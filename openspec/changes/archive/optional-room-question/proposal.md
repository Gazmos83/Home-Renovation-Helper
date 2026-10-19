## Why

The Foreman opens every new piece with "Which room is this for?" and runs no specialist until a room is confirmed. A design file waits too. This assumes every piece belongs in a room. The owner often just wants to see or import a piece, and on 2026-10-17 the room step led into a confusing Intake interview. The owner's decision of 2026-10-17: the Foreman asks first whether the piece should be viewed in a room, and asks which room only on a yes.

## What Changes

- **The first question changes.** Where the Foreman now asks "Which room is this for?", it asks "Would you like to view this piece in a room?". The application reads the answer, with no model call:
  - **yes** (first word yes, ja, yeah, sure, ok or okay): the Foreman asks "Which room is this for?" and the flow continues as today;
  - **an answer naming a stored room or apartment**: a yes with that room, which goes straight to Intake;
  - **anything else**: a no.
- **A no is remembered for the conversation.** A new thread flag records it, and the Foreman does not ask either room question again in that conversation. The owner can still give a room later by naming it, or by sending a plan or photo.
- **After a no, the work goes on without a room:**
  - a design file attached before the answer is imported on that same turn (preview, then yes or no), as the room confirmation does today;
  - Intake and the Designer run without a confirmed room;
  - new and imported pieces are recorded with no room ("No room" on the Pieces page);
  - a bound piece without a room is no longer sent back to Intake for a room.
- **Unchanged:**
  - composing a room, room fit and anything else that needs a room still need one;
  - help questions, price questions and the design-file conflict reply (from `delete-piece`) still come before the room question.
- **Assumptions, TODO(user) for review:**
  - any answer other than a yes or a room counts as a no, so the question is never asked in a loop;
  - a no lasts for the whole conversation.

Ladder: none of the three steps; this is routing and house-file work with no generator change. Agents touched: the **Foreman** (fixed questions and routing, decided by code). Intake and the Designer gain no tools; their rules on a missing room relax when the conversation declined one. The **render guard** and the **bpy allow-list** are **not affected**.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `design-agents`: the Foreman's routing rules (the room offer, yes/no reading, the declined flag, the hand-off of a pending design on a no), Intake's rule that the Designer waits for a room, and where a new or imported piece is recorded.
- `house-file`: the room-delete scenario's next reply becomes the room offer.

## Impact

- `backend/app/db/models.py` and a new Alembic migration: `threads.room_declined` (boolean, default false).
- `backend/app/agent/foreman.py`:
  - a `ROOM_OFFER` constant;
  - answer reading;
  - `room_declined` in the context state;
  - router changes: the fixed questions, the declined hand-off to the Designer with the newest pending design, and skipping the "bound piece has no room → Intake" rule when declined.
- `backend/app/agent/house_file.py`: set and read the flag.
- `backend/app/agent/instructions/foreman.md` and `intake.md`, wherever they quote "Which room is this for?" or say the Designer waits for a room.
- Tests: foreman routing, the house-file flag, the migration, instructions.
- Frontend: no change. The question is an ordinary reply.
- Relation to `delete-piece`: both touch the Foreman's fixed replies. The design-conflict reply comes before the room offer, whichever change lands first.
