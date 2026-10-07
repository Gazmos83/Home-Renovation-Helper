## Why

The app check of 2026-10-06 (`docs/App Check 06-10-2023.md`) found two defects in the listening-wall conversation (thread `daf9cc86…`). The owner's room corrections were routed to the Designer, which does not hold `record_brief`. Its two calls were refused with `this tool is not available to you`, and the reply turned that into "the recording tool won't take an update", so the 76° correction was never saved and the owner was not told plainly. Separately, the conversation view hid four replies, among them the whole design reasoning before `create_piece` and the width maths before two revisions, because text sent alongside a tool call is dropped from the history. The Designer also promised "I'll tell you the moment it's done" about a build, which no part of the app can do.

## What Changes

- **Room corrections go to Intake.** A correction or addition to a room's measurements, corners, angles, ceiling height or openings, or a new or revised plan, goes to Intake even after a brief is confirmed or a piece exists. The Designer stays the choice for changes to the piece.
- **A tool outside the specialist's set is refused by name.** The refusal names the tool and the specialist that owns it (or says the tool is switched off for this conversation) and states that nothing was done. Every specialist is told to pass that on to the owner plainly: nothing was saved, and the next message on the subject reaches the right specialist.
- **No reply is hidden.** A thread's history shows the assistant's text even when it came with tool calls. Tool calls and tool results stay hidden. An answered confirmation stays in the history as one line (subject, summary and the owner's answer) instead of disappearing with the card.
- **No promise after the turn.** No specialist promises to notify the owner later. A turn ends with its reply, and the Builder and Designer point at the Project panel for build status.
- Ladder and agents: chat plumbing around ladder **step 1**. This touches the Foreman's routing text and the tool-refusal path for every specialist, plus the instruction files of Intake, the Designer, the Builder and Lighting & materials. **The render guard and the bpy allow-list are not affected.**

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `design-agents`: room corrections route to Intake after a confirmed brief; a call to a tool the specialist does not hold is refused naming its owner; no specialist promises to report back after the turn.
- `homeowner-chat`: a thread's history shows assistant text sent with tool calls and keeps each answered confirmation as a visible line.

## Impact

- Backend: `app/agent/foreman.py` (refusal text built from the loaded instruction headers and the thread's tool toggles; the answered confirmation is recorded on the gated tool's result), `app/agent/chat.py` (`history`), `app/api/chat.py` (`MessageOut.role` gains `confirmation`), instruction files `foreman.md`, `intake.md`, `designer.md`, `builder.md`, `lighting.md`.
- Frontend: `src/routes/Conversation.tsx` and `src/lib/api.ts` render the `confirmation` history line.
- Tests: `tests/test_foreman.py`, `tests/test_chat_api.py`, `tests/test_instructions.py`, `src/routes/Conversation.test.tsx`.
- No migration, no new dependency, no change to `config/`. Checkpointed threads stay readable, because older answered confirmations simply have no line.
