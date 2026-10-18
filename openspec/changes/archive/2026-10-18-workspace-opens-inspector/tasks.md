## 1. Rail actions

- [x] 1.1 In `frontend/src/components/chat/Rail.tsx`, allow a `Panel` with `onSelect` and no `content`: same icon, name, tooltip and label; clicking closes any flyout and calls `onSelect`; no `aria-expanded`. Verify with a `Rail.test.tsx` case: an action entry opens no dialog and closes an open flyout.

## 2. Panes take over the flyouts

- [x] 2.1 In `frontend/src/routes/Conversation.tsx`, make the Piece and Room header entries actions:
  - Piece → `inspect(latest)`, or `showPane("piece")` when there is no piece;
  - Room → `inspectRoom(slug)`, or `showPane("room")`;
  - return `showPane` from `useConversation`.
  Delete `PiecePanel`, `RoomPanel` and `RoomSection`. Verify with Conversation tests for "Piece icon opens the inspector", "Room icon opens the room view", "No piece yet", "No room confirmed" and "Piece icon opens no flyout".
- [x] 2.2 Add to `PiecePane`:
  - the build-state badge;
  - "N of 15 versions";
  - `DeleteVersion` for the shown version (not approved, queued or running);
  - `PieceVariants` with "Keep this look" sending `keepLookRequest`;
  - the open generator-extension requests.
  Verify with Conversation tests for "Delete from the piece pane", "Keep a look from the piece pane", "Near the limit" and "Unbuilt version offers no control".
- [x] 2.3 Add to `RoomPane` `DeleteCompositionVersion` for the chosen unapproved version and `RoomVariants` for a succeeded version. Verify with a Conversation test that an unapproved room version offers "Delete version N" and an approved one does not.

## 3. Composition builds are followed

- [x] 3.1 Extend the `progress` `refetchInterval` and the `following` flag to poll while `room.versions[0].status` is queued or running. Verify with a Conversation test (fake timers) for "Fresh room version becomes approvable".
- [x] 3.2 Check that refusals show the service's reason: a Conversation test for "Room approval refused" with a mocked 409 whose reason names the piece, asserting no "409" and no `unapproved_pieces` in the pane.

## 4. Checks

- [x] 4.1 In `frontend/`, run `pnpm lint`, `pnpm test` and `pnpm build`; all must pass. Backend unchanged. pytest is deferred to the batch check after the last change of the 2026-10-18 review batch (skip the RunPod/offload tests, use a throwaway `TEST_DATABASE_URL`).
- [x] 4.2 Browser pass, **no render tier**, at 1280 × 800 and 360 × 780:
  - Piece icon → inspector with Approve at the top, and no pop-up;
  - Room icon → room view with Approve;
  - compose a room version and see "Approve version N" appear without a reload;
  - delete an unapproved piece version from the pane;
  - keep a look from the pane.
