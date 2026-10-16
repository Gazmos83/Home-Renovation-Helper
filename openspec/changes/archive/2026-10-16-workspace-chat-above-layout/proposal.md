## Why

In the "Piece and room, chat below" layout the chat is a short strip at the bottom, and its bubbles are split between left (replies) and right (the owner). That is hard to read in a wide, short pane: the eye jumps across the screen for every message. The owner asked (2026-10-16) to put the chat above the piece and the room instead, and to show it as a compact transcript that reads top to bottom on the left.

## What Changes

- **Layout replaced.** **BREAKING (layout name):** "Piece and room, chat below" is replaced by "Piece, room and chat above": the chat pane across the top, the piece pane on the bottom left and the room pane on the bottom right. The menu picture shows the new arrangement. Default sizes: 40 % for the chat and 60 % for the panes below it, and half and half for the piece and the room.
- **Remembered choice carried over.** A browser that remembered "Piece and room, chat below" opens in "Piece, room and chat above". Sizes saved for the old layout are not reused; the new layout starts at its default sizes.
- **Compact chat in this layout only.** Every message sits on the left as a light bubble with its speaker inline in front of the text: "Foreman: …" for a reply, "You: …" for the owner's message. The gap between messages is small. Notices, confirmations, question sets, the decisions note and the waiting bubble also sit on the left. "Chat and piece", "Chat and room" and the phone view keep the current bubbles (replies left, the owner right, forms centred).
- **Composer row.** In this layout the composer's first row is a "You:" label, then the "Describe what you want…" box, then Send (or Stop while a turn runs, or "Send edit" while editing). "Add a plan, photo, design or note", the edit warning and the pending attachments stay below that row.
- **More room for the chat (asked 2026-10-16).** Switching layouts shows the chat scrolled to its last message. The visible "Design Studio" page title is removed from every Design Studio tab; the level-1 heading stays for screen readers. The "Layout" button moves from that title row to the chat pane's header row, after the panel icons. "Delete <title>" moves from its own line to the header row, directly right of the conversation's title.
- **Workspace as home, sign-out in the header (asked 2026-10-16).** **BREAKING (navigation):** the header's "Design Studio" entry is removed. Sign-in, `/`, `/studio`, unknown addresses and developer addresses opened without the developer gate open the Workspace instead of Pieces. The "Home Renovation" name in the header links to the Workspace, so the Help page has a way back. A "Sign out" button at the header's right end ends the session (the existing `POST /auth/logout`) and shows the sign-in page.
- Nothing else in a message changes: formatting, links, attachments, "Edit", "Add to decisions" and the specialists listed under a reply are kept.

No ladder step and no agent is touched; this is Workspace presentation only. The **render guard and the bpy allow-list are not affected**. No backend change.

**Depends on `studio-pricing-and-agent-settings-tabs`.** That change adds the Workspace and its three layouts and is implemented but not yet archived. This change modifies the requirements it adds, so it is archived after that one.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `studio-ui`: the Workspace layout requirement replaces "Piece and room, chat below" with "Piece, room and chat above" and its default sizes and handles; the room-pane requirement names the new layout; the homeowner chat requirement gains the compact left-aligned transcript and the one-row composer for that layout. The Workspace requirement also moves the Layout button into the chat header and scrolls the chat to its last message after a switch; the Design Studio tabs requirement drops the visible page title; the chat-pane header requirement puts the delete action beside the title. "Conversations are not listed in the Studio navigation" is replaced by "The Workspace is the home page", and "The header offers sign-out" is added.
- `dev-panel`: no delta here. The open change `merge-guideline-pages` already rewrites the AI & Agent Settings requirement, so its text there was aligned instead (non-developers land on the Workspace; no "Design Studio" title or header entry), to keep the two changes from overwriting each other.

## Impact

- **Frontend:** `lib/workspaceLayout.ts` (layout id and label, reading an old stored id), `components/studio/LayoutMenu.tsx` (pictogram), `routes/Workspace.tsx` (chat on top, new size ids), `routes/Conversation.tsx` (compact message rendering when the layout asks for it), `components/chat/Bubble.tsx`, `WaitingBubble.tsx` and `Composer.tsx` (a compact variant), `routes/Studio.tsx` (title made screen-reader only, Layout button removed from its row, Workspace as the default tab), `App.tsx` (header entry removed, name links home, Sign out, redirects to the Workspace), `routes/Login.tsx` (lands on the Workspace), `lib/api.ts` (`logout`). Tests: `Workspace.test.tsx`, `LayoutMenu`/`Conversation` tests, `Composer` tests.
- **Dependencies:** none added.
- **Backend:** none.
