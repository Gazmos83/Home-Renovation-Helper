## Why

Pricing Overview and AI & Agent Settings are separate pages, each with its own left rail, beside a Design Studio page that gains a second navigation column in `studio-tile-grid`. The owner asked (2026-10-14) to fold both into the Design Studio, so that one page with one rail and one sub-menu column holds everything except the guidelines and help. The owner also asked (2026-10-14) to work on a conversation, its piece and its room on that same screen, in one of three layouts with panes that can be resized. Today the conversation page shows the chat beside either the piece or the room, in a fixed split, never both.

## What Changes

- **Pricing becomes a Design Studio tab.** The Design Studio rail gains "Pricing" below "Model Library". Its sub-menu views are "Prices", "Snapshots" and "Remnants", with addresses `/studio/pricing/prices`, `/studio/pricing/snapshots` and `/studio/pricing/remnants`. `/studio/pricing` shows Prices. Each view shows what its Pricing Overview tab shows today, unchanged.
- **AI & Agent Settings becomes a developer-only Design Studio tab.** Below a divider at the foot of the rail list, "AI & Agent Settings" is shown only when the developer check passes. Its sub-menu views are the eight existing tabs (Agent Memory, Agent Workflow, Agent Calls, Render Offload, Agent Score, Token Usage, Plugins, Models and Routing). They **keep their `/admin/agents/<view>` addresses and the developer gate**, and are rendered inside the Design Studio layout. The developer route tree stays separate (CLAUDE.md §1).
- **One rail, one title.** The page title is "Design Studio" on every tab. The Pricing Overview and AI & Agent Settings pages, with their own rails and titles, are removed.
- **Header.** **BREAKING (navigation):** the "Pricing Overview" and "AI & Agent Settings" header links are removed. The developer header keeps "Guidelines", "Knowledge" and "Rules". "Design Studio" is marked current on every Design Studio tab, including the developer one.
- **Old addresses forward.** `/pricing`, `/pricing/<tab>`, `/price-list`, `/snapshots` and `/remnants` open the matching Pricing view. `/admin/agents/<view>` addresses are kept as they are. The old `/admin/memory`, `/admin/models` and similar addresses still open their view. A non-developer is still sent to Pieces.
- **Workspace tab.** "Workspace" becomes the first tab on the Design Studio rail. Its sub-menu has "New conversation" at the top, then the conversations, newest first. A conversation opens at `/studio/workspace/<thread-id>`. **BREAKING (navigation):** the standalone conversation page is replaced. `/conversations` and `/conversations/<id>` forward to the Workspace, keeping `?inspect=` and `?room=`. Sign-in still lands on Pieces, and the header still has no Conversations entry.
- **Three layouts.** A layout icon at the right end of the "Design Studio" title row opens a menu of three layouts:
  1. Chat on the left, piece on the right.
  2. Chat on the left, room on the right.
  3. Piece on the left and room on the right, with the chat across the bottom.

  Each split has a drag handle. Dragging it resizes the panes, double-clicking it restores the default split, and the arrow keys move it when it has focus. The chosen layout and each layout's sizes are remembered in the browser.
- **Pane content.** The piece pane is the piece inspector, with its version dropdown. The room pane is the room 3D view, with its version dropdown. The conversation's Tools, Decisions so far, Brief, Project, Piece and Room icons move to the chat pane's header and open their flyouts over the chat. **BREAKING:** the "one side pane at a time" rule and the panes' close buttons go away, because the layout decides which panes are shown.
- **Phone.** Below 1024 px wide, the Workspace shows one pane at a time, chosen from "Chat", "Piece" and "Room" tabs, and the layout icon is hidden.
- **Sub-menu reused.** Pricing and AI & Agent Settings use `studio-tile-grid`'s sub-menu: a column on a laptop and a row of tabs on a phone. They do not use the tile grid, because their content is lists, forms and tables that stay as they are.

No ladder step and no agent is touched. This is Studio navigation and layout only. Opening a pane never starts a turn. The **render guard and the bpy allow-list are not affected**. No backend route changes, and the developer API gate is unchanged.

**Depends on `studio-tile-grid`.** It is applied after that change lands, because it reuses that change's sub-menu and `/studio/:tab/*` routing.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `studio-ui`: the Design Studio requirement grows from three tabs to six: Workspace first, then Pricing, then the developer-only AI & Agent Settings. The Pricing Overview page requirement is replaced by a Pricing tab requirement, and the header loses the "Pricing Overview" entry. A new Workspace layout requirement is added. Four requirements are modified so that the conversation, piece inspector and room view sit in Workspace panes: the conversation rail, the piece reviewed beside the conversation, the room in 3D beside the chat, and conversations in the navigation.
- `dev-panel`: the AI & Agent Settings page requirement is replaced by a developer-only Design Studio tab requirement. The tab keeps its `/admin/agents/*` addresses and gate, and the header loses the "AI & Agent Settings" entry.

## Impact

- **Frontend (Workspace):** `routes/Conversation.tsx` is split into a `useConversation` hook and chat, piece and room panes, with their logic and queries unchanged. New `routes/Workspace.tsx` (layouts and phone tabs), `lib/workspaceLayout.ts`, `components/studio/LayoutMenu.tsx`, and the shadcn-style `components/ui/{resizable,dropdown-menu}.tsx`. `components/chat/Rail.tsx` gains a row variant and shares its label switch live. The shared test setup gains layout stubs for the panels. `Pieces.tsx` conversation links point at `/studio/workspace/<id>`. `Conversations.tsx` is removed, and its "New conversation" moves into the sub-menu.
- **Dependencies:** `react-resizable-panels` (the shadcn Resizable component) and `@radix-ui/react-dropdown-menu`.
- **Frontend (tabs):** `routes/Studio.tsx` (three more rail items, a divider, a developer-only item, sub-menus for both, a `dev` prop and a fixed-tab mode for `/admin/agents/*`). `routes/Pricing.tsx` and `routes/admin/AgentSettings.tsx` lose their rails and titles and become tab bodies that pick a view. `App.tsx` changes the header links, adds redirects from `/pricing*` and `/conversations*`, and points `/admin/agents*` at the Studio. Tests changed: `Studio.test.tsx`, `Pricing.test.tsx`, `admin/AgentSettings.test.tsx`, `App.test.tsx`, `Conversation.test.tsx` (moved to the panes and `Workspace.test.tsx`), `Conversations.test.tsx` (removed) and `Pieces.test.tsx` (link addresses).
- **Backend:** none.
- **Specs:** `openspec/specs/studio-ui/spec.md`, `openspec/specs/dev-panel/spec.md`.
- **Order:** apply after `studio-tile-grid` is archived. That change's synced Design Studio requirement is the base for this change's MODIFIED requirement.
