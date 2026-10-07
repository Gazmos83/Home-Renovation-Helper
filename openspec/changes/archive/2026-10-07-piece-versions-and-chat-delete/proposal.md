## Why

After `piece-inspector` the owner could not get a new version of the Murphy bed to see the dimension lines and views (2026-10-07):
- The Designer's `revise_package` refuses a revision with no changes ("state at least one change").
- An attached design file can only become a new piece. With its id already in use, or in a conversation already bound to a piece, the import is refused.
- In a new conversation, "Revise it" was sent to Intake by a routing rule (no bound piece, no brief), and Intake answered with an empty message.

So there is no way to rebuild a piece as-is, or to bring in an updated design file for it. The owner also asked for a way to delete conversations. That is already specified, unbuilt, in `studio-chat-polish`, and moves here so it arrives sooner (owner's choice, 2026-10-07).

## What Changes

- **Rebuild unchanged (Designer).** A new gated tool `rebuild_piece` takes a piece's package id. It previews "version N+1, rebuilt unchanged from version N" and, on `yes`, records the next version with the change line `rebuilt unchanged from version N` and starts the headless build. The point is to pick up generator changes, such as new views or dimension lines. Nothing in the document changes.
- **Import as the next version (Designer).** A new gated tool `import_design_version` takes an attached design file's upload id and an existing piece's id. The file is read and checked exactly as `import_design` checks it. The preview shows the new design's summary and names the version it follows. On `yes`, the next version is recorded with the change line `imported from <file name>, replacing version N` and is built. It is refused in a conversation bound to a different piece. `import_design`'s refusals for an id in use, or for a conversation that already has a piece, now point to importing as the next version.
- **Routing.** A thread with no bound piece and no brief may go to the Designer when the Foreman chose the Designer and the owner's message, or the reply before it, names a piece in the house file by id or name. "Revise it" after the Designer named `murphy-bed` therefore reaches the Designer, not Intake.
- **No empty reply.** A specialist whose final answer has no text and no tool call is asked once more. If the second answer is also empty, the turn ends with a fixed sentence naming the role and asking the owner to rephrase, so the owner always sees an answer.
- **Delete a conversation.** This is moved from `studio-chat-polish`, with one difference: a delete during a running turn is refused instead of discarding the turn's result.
  - The Conversations page offers a delete action with a confirmation that names the conversation and says its pieces are kept.
  - `DELETE /chat/threads/{id}` removes, in order, the conversation memory (checkpointer first), then the index entry, which cascades its uploads and tool settings, then the uploads' files.
  - Pieces, versions, renders, rooms, preferences, reviews, feedback and recorded usage stay.
  - A delete is refused while a turn is running on that thread, so no checkpoint is written after it.
- `studio-chat-polish` is edited to drop its delete tasks and to point here; its spec text already describes the same delete.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `design-agents`:
  - the routing rule for a thread without a piece or brief;
  - the Designer's new `rebuild_piece`;
  - a specialist's empty answer is retried once and never shown empty.
- `design-import`:
  - `import_design`'s refusals point to the version import;
  - the new `import_design_version`.
- `homeowner-chat`: a conversation can be deleted, refused while a turn runs.
- `studio-ui`: the Conversations page's delete action with its confirmation.

## Impact

- **Ladder and agents.** Step 1 only. A rebuild or an imported version is built headless like any revision; no render is started.
  - **Agents touched:**
    - the Foreman's routing rule, in code;
    - the Designer, with two new tools and its instruction file;
    - every specialist, through the empty-answer retry.
  - The Builder, Reviewer, Lighting and Researcher get no new tool.
- **Render guard and bpy allow-list.** Unaffected: no render path and no live script changes.
- **Backend:**
  - `plugins/revise_package/` gains `rebuild_piece` in its manifest and tool;
  - `plugins/design_import/` gains `import_design_version`;
  - `app/agent/foreman.py`: the routing rule, a "piece named" flag from `load_house`, and the empty-answer retry;
  - `app/agent/house_file.py`: `delete_thread`;
  - `app/api/chat.py`: `DELETE /chat/threads/{id}` and a per-process set of threads with a running turn;
  - `app/agent/instructions/designer.md` and `foreman.md`.
- **Frontend:** `lib/api.ts` (`deleteThread`) and `routes/Conversations.tsx` (delete with confirmation).
- **Data:**
  - No migration: `uploads` and `thread_tool_settings` already cascade from `threads`, and `plugin_invocations.thread_id` is `ON DELETE SET NULL`.
  - `render_runs.thread_id` has no foreign key and is left as a dangling id.
  - A deleted conversation cannot be restored.
- **`studio-chat-polish`:**
  - its tasks 1.2 (`delete_thread`), 4.2 (the `DELETE` route), 8.2 (`deleteThread`), 8.4 (delete in the list) and 9.1 (the delete step) are narrowed to what remains;
  - its homeowner-chat delta's sentence on a running turn is aligned with the refusal here.
