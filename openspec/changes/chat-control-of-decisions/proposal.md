## Why

The "Decisions so far" note can be changed only from the panel. Telling the assistant in the chat to "forget the door decision" or "note that the shelves are 18 mm" changes nothing in the note until a later refresh rewrites it, and that refresh can bring the line back. The owner should be able to manage the note in the place where decisions are made.

## What Changes

- A new gated tool, `edit_decisions`, lets an assistant add, change or delete one row of the active note on the owner's request. It pauses with `interrupt()` and shows the exact before and after, and nothing is written until the owner answers "yes" (the same pattern as `revise_package`).
- The assistant uses the tool only when the owner's own message asks for a row to be added, changed or deleted. It may offer, but it never acts unprompted, and never changes the note as a side effect of another request.
- The owner can also record a decision straight from a chat message: an **Add to decisions** button on a message opens a pre-filled Topic and Decision row to adjust and save. It uses the same append as **Add Topic Decision**, needs no model call, and needs no further confirmation because the owner sees and saves the row.
- The tool takes the thread from the session, never from a model argument. It reuses the panel's row rules, so a chat edit and a table edit produce the same note text, and the same save path with the same checks: neutralised text, 8000-character limit, at least one row, owner-marked.
- A row is named by its topic and, when two rows share a topic, by its position. An unknown or ambiguous name is refused with the matching rows listed, and nothing is written.
- The tool is for the owner's own corrections. The model cannot use it to change a figure's meaning: figures in the note stay records, and dimensions and prices still come from the spec and the house file.
- The Designer's instructions say when to use it and to relay a refusal in plain words; nothing else about routing changes.
- The panel shows the change without a reload: the chat's reply ends a turn, and the panel's note query is refreshed then.

Ladder step: none (no spec JSON, generator or Blender change). Agent touched: Designer (the Foreman routes to it). The render guard and the bpy allow-list are not affected.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `homeowner-chat`: the owner can add, change and delete rows of the "decisions so far" note by explicitly asking in the chat, behind a confirmation, and can record a decision from a chat message with a button.

## Impact

- Backend: new plugin `backend/plugins/edit_decisions/` (manifest and tool), row helpers shared with the note route in `backend/app/agent/` (a Python port of the panel's row rules), `designer.md`, tool toggle tests.
- Frontend: an **Add to decisions** button on chat messages that opens the panel's add row pre-filled; refresh the note query when a turn ends, in `routes/Conversation.tsx`; the row rules in `DecisionsNote.tsx` stay the display's own.
- No migration and no new dependency. Tokens: the tool's schema adds a small amount to the Designer's calls only.
