## 1. Frontend

- [x] 1.1 In `frontend/src/routes/Conversation.tsx`, replace the "Nothing said yet" line with a left `Bubble` signed `personaOf("foreman")` reading "Little Homey here, how can I help?", under the same condition. Verify with `Conversation.test.tsx` cases for "Greeting in a new conversation" and "Greeting is not part of the history", and update any test that expects "Nothing said yet".

## 2. Checks

- [x] 2.1 `pnpm lint`, `pnpm test`, `pnpm build`
- [x] 2.2 Browser pass: a new conversation shows the greeting bubble in the normal and compact layouts; it disappears after the first message
  - Note 2026-10-19: checked headless in Chrome: the greeting shows in both layouts and nothing is stored. Disappearing after the first message is covered by the unit test only, because a live turn would call a model.
