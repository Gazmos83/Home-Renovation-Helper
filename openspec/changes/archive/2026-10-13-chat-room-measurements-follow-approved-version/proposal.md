## Why

The owner found that the chat bot quotes room measurements that differ from the approved room version's inspector view (Wohnen, 2026-10-12). Cause, from the code: the room block in the chat prompt (`prompts.house_note`) gives only the bounding box of the house-file corners (`_size`, "6200 × 6064 mm") and the ceiling height, while the inspector shows each wall's own length (`compositions.room_dimensions`, Wohnen v2: 6200, 5700, 2700, 2241 and 6199 mm). The room is not a rectangle, so the two never agree. The composition note lists items but no measurements, and nothing ties the numbers the bot sees to the version the owner approved.

## What Changes

- The chat's room block states each wall's length and each ceiling height, read from the stored document of the room's approved composition version (the same function the inspector uses), labelled with that version; with no approved version it uses the latest version and says so; with no composition it keeps today's house-file figures.
- Because the block is built on every turn, a newly approved version's measurements reach the chat on the next turn; the prompt tells the bot to prefer this block over measurements it quoted earlier or that sit in the conversation note.
- The bot can read the inspector's dimensions of a named room version on request, to confirm or correct a figure in the chat (read-only; it never writes a dimension).
- Placement checks (`room_fit`, `compose_room`) use that same approved (else latest) version's room plan — corners, openings and height — so a door or wall length that blocks a piece matches the inspector, not a stale house-file opening list. With no composition they keep today's house-file room.
- Not changed: nothing writes a dimension back to the house file or the spec (ladder step 3 rule); generators and the render guard are untouched.

## Capabilities

### New Capabilities

### Modified Capabilities
- `homeowner-chat`: the room block carries per-wall lengths from the approved version and stays current after approval.
- `room-composition`: a read-only way to give a version's inspector dimensions to the chat; placement tools read the same version's plan for fit checks.

## Impact

`backend/app/agent/prompts.py` (`house_note`), `backend/app/agent/foreman.py` (room block assembly), `backend/app/compositions.py` (reuse `room_dimensions`, placement room plan), `room_fit` and compose `_rooms_in_scope`, a read-only tool under the existing plugin layout, tests for each. No schema, migration or frontend change.
