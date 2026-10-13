## Why

The Project flyout opens over the chat. Pressing "Inspect version N" or "Inspect <room>" in it opens the inspector beside the chat, but the flyout stays open and covers part of the view the owner just asked for. The owner has to close it by hand every time.

## What Changes

- Choosing "Inspect version N" or "Inspect <room>" in the Project flyout closes the flyout and shows the inspector.
- Nothing else closes the flyout: other buttons in it (approve, delete, use a look) leave it open, and the Tools and Decisions flyouts are unchanged.
- The inspector's own controls and the chat's Inspect buttons (build notices, Review) are unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-ui`: the Project flyout closes when an inspector is opened from it.

## Impact

- Frontend only: `routes/Conversation.tsx` (the Project panel's inspect handlers) and `Conversation.test.tsx`; tests that click "Inspect Hall" in the panel after opening a version need to reopen the panel.
- No backend, migration or setting change.
