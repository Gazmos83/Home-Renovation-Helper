## Why

The owner asked on 2026-10-19 that a conversation open with a greeting from Little Homey, instead of the grey "Nothing said yet. Describe the piece you want." line.

## What Changes

- A conversation with no messages shows a reply bubble signed "Little Homey" that reads "Little Homey here, how can I help?", in place of the "Nothing said yet" line.
- The greeting appears only on the screen. It is not saved in the thread's history, no model call is made, and no agent sees it. Once the owner sends the first message it is no longer shown, like the line it replaces.

Ladder step: none (no spec, generator or Blender change). Agents touched: none. Render guard and `bpy` allow-list: not affected.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-ui`: an empty conversation shows Little Homey's greeting in the messages box instead of the "Nothing said yet" line.

## Impact

- `frontend/src/routes/Conversation.tsx` (the empty-state line) and `Conversation.test.tsx`.
- Depends on the persona names from `meet-the-crew` (`personaOf`), which is applied but not yet committed.
