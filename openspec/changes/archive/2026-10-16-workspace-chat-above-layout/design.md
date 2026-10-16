## Context

`studio-pricing-and-agent-settings-tabs` (implemented, not archived) added the Workspace. `lib/workspaceLayout.ts` holds the three layout ids (`chat-piece`, `chat-room`, `piece-room`), remembers the choice in `localStorage` under `studio.workspace.layout`, and exposes `useWorkspaceLayout()` and `hasPane()`. `routes/Workspace.tsx` builds the layouts from `react-resizable-panels` groups whose sizes are saved under their group id (`workspace.piece-room.rows`, `workspace.piece-room.cols`). Each pane's element is rendered once and moved into the slot the layout chooses, so switching keeps the chat's state. `LayoutMenu.tsx` draws a 32 × 20 pictogram per layout.

The chat pane (`ChatPane` in `routes/Conversation.tsx`) renders replies and owner messages through `components/chat/Bubble.tsx` (`side` left/right/center, speaker above), the waiting bubble through `WaitingBubble.tsx`, and the composer through `Composer.tsx` (message box on its own row, Send and attach on the row below). The messages list uses `space-y-4` (16 px).

## Goals / Non-Goals

**Goals:**
- Swap the third layout for chat-on-top without disturbing the other two layouts or the phone view.
- Give that layout a compact chat and a one-row composer while keeping every message control.

**Non-Goals:**
- No change to message content, formatting, decisions, edit, notices or turn handling.
- No new layout beyond the three; no per-layout chat style setting.

## Decisions

**1. Rename the id to `chat-above`, read the old id as the new one.** `WorkspaceLayout` becomes `"chat-piece" | "chat-room" | "chat-above"`, label "Piece, room and chat above". `read()` maps a stored `"piece-room"` to `"chat-above"` (and the next `setWorkspaceLayout` stores the new id). `hasPane()` treats `chat-above` as having both panes. *Alternative:* keep the `piece-room` id with a new label — rejected, since the id would describe the opposite arrangement.

**2. New size group ids.** The vertical group becomes `workspace.chat-above.rows` (chat pane first, `40%`; bottom pane `60%`) and the horizontal one `workspace.chat-above.cols`. Old `workspace.piece-room.*` sizes are left unread, so the new layout starts at its defaults as the spec asks. Handle names: "Resize the chat above the piece and room" and the existing "Resize the piece and the room". Leftover old keys in `localStorage` are harmless and not deleted.

**3. The chat pane decides compactness itself.** `ChatPane` computes `compact = wide && layout === "chat-above"` from `useWorkspaceLayout()` and `useMediaQuery(WORKSPACE_WIDE)`, the same hooks `Workspace.tsx` already uses. No prop is threaded through the moved pane element, so switching layouts re-renders the chat in place and keeps the half-typed message. *Alternative:* a React context from `Workspace` — rejected as a new pattern for one boolean.

**4. A `compact` flag on the existing chat components.**
- `Bubble` gets `compact?: boolean`. Compact: always left (`mr-auto`), a flex row with the speaker as an inline, non-shrinking `"<speaker>:"` label (Oswald, as today) followed by the body; the body keeps its border-only card look (`border bg-card`, the owner's filled `bg-primary` dropped), tighter padding (`px-3 py-1.5`).
- `OwnerMessage` and the reply bubble pass `compact`; centred items (confirmation notes, answers, the pending confirmation card) get `mr-auto` instead of `mx-auto` when compact.
- The messages list uses `space-y-2` (8 px) when compact, `space-y-4` otherwise.
- `WaitingBubble` gets `compact` for padding only; it is already on the left.
- `Composer` gets `compact?: boolean`: the first row becomes a flex row of a `<Label>` "You:" bound to the message box, the box (`flex-1`) and the Send/Stop/Send edit button; the attach label stays on the row below. The `aria-label="Message"` and placeholder stay, so existing tests keep finding it.

*Alternative:* a separate `CompactBubble` component — rejected; one flag keeps the formatting path shared, which is what the spec requires.

**5. Pictogram.** For `chat-above`: C box across the top (`y=1,h=6`), P and R boxes below (`y=9,h=10`).

**6. Header changes (added 2026-10-16).** `Studio.tsx` keeps its `<h1>Design Studio</h1>` with `sr-only`, so the page keeps an accessible name and the existing heading tests hold, and drops the `LayoutMenu` from that row. `ChatPane` renders `LayoutMenu` after the `Rail` in its header; `LayoutMenu` already hides itself on a narrow screen. The header's left cluster becomes the title, then `DeleteConversation`; the cluster wraps, and the delete confirmation takes a full line (`basis-full`) when shown. *Alternative:* removing the `<h1>` entirely — rejected, it leaves the page without a level-1 heading.

**7. Scroll after a switch.** `ChatPane` scrolls the messages box to its end in a layout effect keyed on the layout, and sets `atBottom` so the box keeps following. The pane's element is moved between slots on a switch, and a detached element loses its scroll position, so restoring "where the owner was" is not available cheaply; the owner asked for the last message.

## Risks / Trade-offs

- [The inline speaker label beside a long formatted reply (tables, headings) narrows the reply's width a little] → the label is short and non-shrinking; tables already scroll horizontally inside the bubble.
- [The MODIFIED delta targets a requirement only present in the unarchived base change] → archive `studio-pricing-and-agent-settings-tabs` first; `openspec validate --strict` already notes this.
- [A remembered `piece-room` choice] → mapped on read, covered by a test.

## Migration Plan

Frontend-only. The stored layout id is mapped on read; no data migration. Rollback is reverting the commit; a stored `chat-above` would then fall back to the default layout through the existing `isLayout` check.
