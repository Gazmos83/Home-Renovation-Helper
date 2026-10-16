No task renders; no render tier is involved.

## 1. Layout

- [x] 1.1 In `frontend/src/lib/workspaceLayout.ts`, replace `piece-room` with `chat-above` labelled "Piece, room and chat above", map a stored `piece-room` to `chat-above` on read, and make `hasPane` true for both panes in `chat-above`; verify with a new `lib/workspaceLayout.test.ts` (old id read as new, unknown id gives the default, `hasPane`).
- [x] 1.2 In `frontend/src/routes/Workspace.tsx`, build `chat-above` as a vertical group `workspace.chat-above.rows` with the chat pane first at 40 % and a bottom pane at 60 % holding the horizontal group `workspace.chat-above.cols` (piece, room, half and half); name the vertical handle "Resize the chat above the piece and room"; verify with `Workspace.test.tsx` updated for "Choose a layout" (chat before the piece and room in document order, handle values 40 and 50), "Chat expanded downwards" (arrow down grows the chat) and "Old layout remembered".
- [x] 1.3 In `frontend/src/components/studio/LayoutMenu.tsx`, draw the chat box across the top and the piece and room boxes below for `chat-above`; verify the menu test lists "Chat and piece", "Chat and room", "Piece, room and chat above" in order.

## 2. Compact chat

- [x] 2.1 Add a `compact` flag to `components/chat/Bubble.tsx` (left-aligned, inline "<speaker>:" before the body, border-only light bubble, tighter padding) and to `WaitingBubble.tsx` (padding only); verify with a new `Bubble.test.tsx` (compact owner bubble is left, has no filled primary background, speaker and text in one row).
- [x] 2.2 In `routes/Conversation.tsx`, compute `compact` from `useWorkspaceLayout()` and `useMediaQuery(WORKSPACE_WIDE)`; pass it to reply and owner bubbles and the waiting bubble, align confirmations, answers and the pending confirmation card left, and use an 8 px gap between messages when compact; verify with `Conversation.test.tsx` or `Workspace.test.tsx` cases for "Compact transcript" and "Other layouts unchanged" (a half-typed message survives the switch).
- [x] 2.3 Add a `compact` flag to `components/chat/Composer.tsx` putting a "You:" label, the "Describe what you want…" box and Send/Stop/"Send edit" on one row, with the attach control, edit warning and pending attachments below, and pass it from the chat pane; verify with a test for "Compact composer" and that existing composer tests still pass.

## 4. Header and scroll (asked 2026-10-16)

- [x] 4.1 In `routes/Studio.tsx`, make the "Design Studio" `<h1>` screen-reader only and drop the Layout button from its row; in `ChatPane`, render the Layout button after the panel icons; verify with Studio/Workspace tests for "No page title" and "Layout button in the chat header".
- [x] 4.2 In `ChatPane`, put `DeleteConversation` on the header row directly right of the title, with its confirmation on a full line below; verify with a test for "Delete beside the title" and that the existing delete tests pass.
- [x] 4.3 In `ChatPane`, scroll the messages box to its end when the layout changes; verify with a Workspace test for "Last message after a switch".

## 5. Home page and sign-out (asked 2026-10-16)

- [x] 5.1 Make the Workspace the default: `Studio.tsx` defaults and unknown tabs to `workspace`; `App.tsx` sends `*`, `/` and non-developer developer addresses to `/studio/workspace`; `Login.tsx` lands on `/studio/workspace`; verify with App/Studio tests for "Sign-in lands on the Workspace", "Home address" and the dev-panel "Not a developer" scenarios.
- [x] 5.2 Remove the "Design Studio" header entry and its `ALSO_CURRENT` handling, and make "Home Renovation" a link to `/studio/workspace`; verify with App tests for "Navigation", "Nav without Conversations" and "Name in the header".
- [x] 5.3 Add `api.logout()` and a "Sign out" button at the header's right end that posts it, then shows the sign-in page, or shows the refusal beside the button; verify with App tests for "Sign out" and "Sign-out fails".

## 3. Checks

- [x] 3.1 Run `pnpm lint`, `pnpm test` and `pnpm build` in `frontend/`; all pass. Record the counts here.
  Run 2026-10-16: `pnpm lint` clean, `pnpm test` 457 passed in 47 files, `pnpm build` built.
  Rerun 2026-10-16 after groups 4 and 5: `pnpm lint` clean, `pnpm build` built, `pnpm exec vitest run --maxWorkers=4` 467 passed in 47 files. Two earlier full runs at a load average near 12 each had 3 timing failures in files this change does not touch (`admin/Knowledge.test.tsx`, `Pieces.test.tsx`, `Rooms.test.tsx`), a different set each time; those files pass on their own.
- [x] 3.2 Browser check at 1280 × 800: choose "Piece, room and chat above", send a message, confirm the compact transcript and one-row composer, drag the handle below the chat, switch back to "Chat and piece"; and at 360 × 780 confirm the phone tabs keep the left/right bubbles. Record the result here.
  Browser pass 2026-10-16: headless Chromium through Python Playwright 1.63, against a fresh `vite build` served by `vite preview` on 5211, with the API stubbed in the page (a frontend-only change; the owner's 8000 / 5173 and database untouched). A conversation of two owner messages, two replies (one with a list and a table) and a draft notice. 18 of 18 checks passed, with no page errors:
  - **1280 × 800:** "Piece, room and chat above" puts the chat across the top and the piece and room panes side by side below it, at 40 % and 50 / 50. Every message, the notice included, starts at the same left edge (x 282), with 8 px between messages. "You:" and "Foreman:" sit on the first line of their bubbles, and the owner's bubble has the reply's light background. The table is still a table. "You:", the "Describe what you want…" box and Send share one row, and the attach link is below it.
  - **Handles:** dragging the handle below the chat down grows the chat (40 → 55.8), and dragging it up stops at 20. A reload keeps the layout at 20, and a double-click restores 40.
  - **Switching back:** in "Chat and piece" the owner's messages are on the right again, and the half-typed "Also lower" is kept. A stored `piece-room` opens chat above.
  - **360 × 780:** the bubbles stay left and right, there is no Layout button, and the page does not scroll sideways (360 / 360).
  - **Found during this pass:** after any layout switch the messages box was scrolled to the top (scrollTop 0), between the two old layouts as well, because moving the pane's element resets its scroll. Task 4.3 fixed it at the owner's request.
  Second pass 2026-10-16, same setup, for groups 4 and 5: 32 of 32 checks passed, with no page errors. `/` lands on `/studio/workspace`. The header holds "Home Renovation" (a link to the Workspace) and "Help", with no "Design Studio" entry and "Sign out" at its right end. The level-1 "Design Studio" heading is screen-reader only, so the messages box starts at y 133 instead of 233. "Delete Hall bench" sits on the header row right of the title, and its confirmation takes the line below. "Layout" sits after the Room icon at the end of the chat header. After each switch (to "Chat and room", "Chat and piece" and "Piece, room and chat above") the chat shows its last message. From Help, "Home Renovation" returns to the Workspace. At 360 × 780 "Sign out" is reachable and the page does not scroll sideways. "Sign out" posts the logout and shows the sign-in page without the header, and `/studio/workspace` then shows sign-in too.
- [x] 3.3 Archive after `studio-pricing-and-agent-settings-tabs` is archived, and verify with `openspec validate workspace-chat-above-layout --strict` that the archive notice about the missing Workspace requirement is gone.
