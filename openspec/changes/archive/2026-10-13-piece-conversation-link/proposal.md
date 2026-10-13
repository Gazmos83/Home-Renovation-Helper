## Why

A conversation that can hold several builds mixes pieces in one chat, while the owner designs one piece at a time. Rooms already hold many pieces; the chat should not. Entry into chat still lives on a Conversations list, so the piece the owner is looking at is not the place to open or start its talk.

## What Changes

- **One piece per conversation.** A conversation is about at most one piece. Creating or revising a second piece in a conversation that already has a bound piece is refused in plain words; naming another house-file piece no longer joins it to the conversation or switches the active build. Rooms may still hold many pieces.
- **Conversation link on each piece.** The Pieces page shows a conversation link directly under each piece's header. When that piece already has a conversation, the link opens it. When it has none, the link starts one bound to that piece and opens it.
- **"Create A New Piece" on the Pieces page.** A button at the top of the page starts an unbound conversation and opens it, so the owner can describe a new piece there. The first confirmed `create_piece` (or import) binds that conversation to the new piece.
- **Conversations leave the nav.** The Conversations item is removed from the Studio navigation. Routes `/conversations` and `/conversations/:threadId` stay reachable by deep link and from the piece links. Delete of a conversation moves onto the conversation view itself so it remains available without the list in the nav.
- Ladder and agents: **ladder step 1** (spec / house-file / chat binding). Touches the Foreman (no multi-build switch or "Which piece do you mean?" for builds of the same conversation), Intake/Designer only insofar as a second piece is refused. **The render guard and the bpy allow-list are not affected**; no render is started by this change.
- **BREAKING (behaviour):** a conversation no longer accumulates a list of builds; the multi-build house-file and Foreman rules from `conversation-projects` are replaced by one bound piece.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `studio-ui`: Pieces page gains "Create A New Piece" and a per-piece conversation link under the header; Conversations leaves the nav; conversation delete is available on the conversation view.
- `homeowner-chat`: starting a conversation may bind an existing piece; a second piece in a bound conversation is refused; list/start from the Conversations page is no longer the primary owner path (routes remain).
- `house-file`: a conversation holds at most one piece; pieces report their conversation for the Pieces page; multi-build list and active-build switching go away.
- `design-agents`: Foreman no longer asks "Which piece do you mean?" among builds of the same conversation, and naming another house-file piece does not join it to a bound conversation.

## Impact

- Backend: `house_file` thread/piece binding (`create_thread`, `add_build` / `set_active_build` / builds list), Foreman routing, `create_piece` / `revise_package` / design-import when a conversation is already bound to another piece, packages list (or equivalent) exposing each piece's `thread_id`, chat start with `package_id` for an existing piece.
- Frontend: `Pieces.tsx` (button + per-piece link), `App.tsx` nav, `Conversation.tsx` (delete), `api.ts`, tests and a recorded browser pass on the Pieces page.
- Docs: CLAUDE.md §9a wording for one piece per conversation.
- Tests: pytest for binding and refusal; Vitest for Pieces and Conversation; no Blender, no render tiers.
- No new dependency, no migration required if the existing `thread.package_id` and `thread_pieces` can express one row per thread (legacy multi-build rows stay readable as the bound piece only, or are cleaned in code without a schema change). Confirm in design.
- Related: supersedes the multi-build part of archived `conversation-projects`; complements piece-first workflow and the Pieces page.
