## Context

`Conversation.tsx` holds the open flyout in `panel` state and passes `inspect` and `inspectRoom` to `ProjectPanel` as `onInspect` and `onInspectRoom`. Build notices call `inspect` directly from the chat, where no flyout is open.

## Decisions

1. **Close in the Project panel's two handlers only.** The rail's panel entry passes wrappers that call `inspect` or `inspectRoom` and then `setPanel(null)`. `inspect` and `inspectRoom` themselves stay unchanged, so notices, Review and the inspector's own version dropdown behave as before and nothing else can close a flyout by accident.
2. **Room inspection is included.** The request says "the inspector view"; the room view is opened from the same flyout in the same way, so both close it. Assumed; easy to narrow.

## Risks / Trade-offs

- Existing tests that open the panel once and click Inspect twice must reopen it; they change only for that reason.
