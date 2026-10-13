# Chat room measurements vs. inspector view — discussion notes (2026-10-12)

OpenSpec change: `openspec/changes/chat-room-measurements-follow-approved-version/` (proposal, design, tasks, delta specs for `homeowner-chat` and `room-composition`). Planning only; no code changed. `openspec validate` passes.

## What's wrong
- The chat prompt shows each room as a bounding box plus ceiling height. Wohnen comes out as "6200 × 6064 mm".
- The inspector shows each wall's own length: 6200, 5700, 2700, 2241 and 6199 mm for approved version 2.
- Wohnen isn't a rectangle, so those two sets of numbers can never agree.
- The corners in the house file and in approved version 2 are currently identical, so the data isn't stale. The gap is how the chat prompt describes the room.
- The composition note lists the pieces in a room but no measurements.
- Today's conversation itself was not read; the cause comes from the code and stored room data.

## What the change proposes
- **Stay current on approval:** the chat's room block is rebuilt every turn from the approved version's stored document, using the same function the inspector uses (`compositions.room_dimensions`). Approving a new version updates the chat from the next message, with no copying into the house file. Without an approved version it uses the latest version and says it isn't approved. The prompt also tells the bot to prefer this block over older quotes and the conversation note.
- **Read inspector dimensions:** a small read-only tool lets the bot look up a named version's wall lengths and ceiling heights to confirm or correct a figure. The room comes from the conversation's scope, not from the model, and it never writes a dimension.
- **Nothing else changes:** no schema, migration, frontend, generator or render-guard changes.

## Open decision
Approval is assumed not to write the composition's numbers back to the house-file room, so there is only one source for them. Decide whether you want it to.

## Next step
Say "apply chat-room-measurements-follow-approved-version" or run `/opsx:apply`.
