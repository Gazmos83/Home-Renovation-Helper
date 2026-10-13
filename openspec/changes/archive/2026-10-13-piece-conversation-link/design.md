## Context

See proposal.md for motivation. Today a conversation can hold many builds (`thread_pieces` plus `Thread.package_id` as the active build); the Foreman can switch the active build by name and ask "Which piece do you mean?". Chat entry lives on a Conversations nav item with "New conversation". The Pieces page lists each piece's card (`<h2>` id, picture, room, versions) with no link into chat. `POST /chat/threads` already accepts an optional `package_id`; `GET /packages` returns `package_id`, `versions`, and `room`, but no conversation id.

## Goals / Non-Goals

**Goals:**
- Enforce one bound piece per conversation in the house file and tools.
- Expose each piece's conversation id on the pieces list.
- Put "Create A New Piece" and per-piece conversation links on the Pieces page; remove Conversations from the nav; land sign-in on Pieces; delete from the conversation view.

**Non-Goals:**
- Changing room composition (many pieces per room stays).
- Dropping the `/conversations` routes or rewriting the conversation view layout beyond delete + nav entry.
- A schema migration solely to drop `thread_pieces` (keep the table; treat one row / `package_id` as the binding).
- Changing render guard, bpy allow-list, or any specialist's model slot.

## Decisions

1. **Binding source of truth stays `Thread.package_id`.**  
   On bind (start with `package_id`, or first successful `create_piece` / revise / import on an unbound thread), set `Thread.package_id` and ensure a single matching `thread_pieces` row for summaries. Do not add further builds. `set_active_build` for a different package on a bound thread becomes a no-op that callers must not use; tools refuse instead.  
   *Alternative considered:* drop `thread_pieces` in a migration. Rejected for this change — summaries already key by package id; keeping the table avoids a migration and preserves legacy rows.

2. **Lookup: one conversation per piece.**  
   Resolve a piece's conversation as the thread whose `package_id` equals that piece, newest `last_turn_at` if legacy duplicates exist. Starting a thread with a `package_id` that already has such a thread returns 409 with a stated reason. The Pieces page opens the existing id; it never creates a second.

3. **Pieces list carries `thread_id`.**  
   Extend `GET /packages` (and the frontend `PieceSummary`) with `thread_id: string | null`. Compute in the packages list handler from the house file (query threads by package ids). No separate endpoint.

4. **Create A New Piece = unbound `createThread()`.**  
   Same as today's new conversation, opened from Pieces. First confirmed create/import binds it. Empty-state copy on Pieces points at the button.

5. **Nav and default route.**  
   Remove `["/conversations", "Conversations"]` from the homeowner nav. Change post-login and fallback navigations that today go to `/conversations` to `/pieces`. Keep Conversations route components for deep links; the list page may remain unused in the nav. Delete control moves onto `Conversation.tsx` (confirm → `deleteThread` → navigate to `/pieces`).

6. **Foreman and tools.**  
   Remove the multi-build ambiguity fixed question and the "join named house-file piece while already bound" path. Unbound + named piece with no conversation still binds (Designer path). Unbound + named piece that already has a conversation: fixed plain-words reply, no bind. `create_piece` / design-import refuse when `thread.package_id` is set to a different id.

7. **Legacy multi-build threads.**  
   At read time, treat `Thread.package_id` as the only bound piece; ignore other `thread_pieces` rows for routing and house_note "other builds". No automatic cleanup required for correctness; optional one-off prune of extra `thread_pieces` rows is out of scope unless tests need a clean fixture.

## Risks / Trade-offs

- **[Risk] Orphan unbound conversations** (Create A New Piece then abandon) clutter deep-link list → Mitigation: delete on the conversation view; owner can remove them. No auto-delete.
- **[Risk] Legacy threads with several builds** confuse prompts if "other builds" code remains → Mitigation: house_note and Foreman read only `package_id`; update tests that assumed multi-build.
- **[Risk] Sign-in redirect to Pieces surprises muscle memory** → Mitigation: owner decision; Conversations deep links still work.
- **[Trade-off] Keeping `thread_pieces`** leaves a multi-build-shaped table for a one-piece rule → Acceptable; avoids migration and keeps per-piece summaries.

## Migration Plan

1. Ship backend binding refusals and `thread_id` on the packages list.
2. Ship frontend Pieces button/links, nav change, conversation delete, login redirect.
3. No Alembic migration. Rollback: revert the commits; old multi-build behaviour returns; `thread_id` field ignored by old clients.

## Open Questions

None.
