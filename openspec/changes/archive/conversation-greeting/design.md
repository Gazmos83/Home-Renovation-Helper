## Context

`Conversation.tsx` shows `<p>Nothing said yet. Describe the piece you want.</p>` when a thread has no messages and nothing is being sent. Replies are drawn with `Bubble side="left" speaker={personaOf(m.speaker)}`; `personaOf("foreman")` is "Little Homey".

## Decisions

- **Screen only, not stored.** Saving the greeting as a Foreman reply would put it in every thread's history and every agent's context, and would mean writing a message when a thread is created. Drawing it in the empty state needs no backend change and no model call. This matches the owner's "screen only" choice for personas in `meet-the-crew`. TODO(user): say if the greeting should instead be stored as the first reply.
- **Same bubble as a reply.** The greeting uses `Bubble` with `speaker={personaOf("foreman")}`, so it follows the normal and compact layouts like any other reply.
- **Shown only while the thread is empty.** It keeps the existing condition (`messages.length === 0 && !showOptimistic`), so it disappears when the owner's first message appears.

## Risks / Trade-offs

- Once the first message is sent the greeting disappears, so the history does not begin with it. This is accepted because the greeting carries no information.
