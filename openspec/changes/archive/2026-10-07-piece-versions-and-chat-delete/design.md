## Context

The owner's Murphy bed conversations on 2026-10-07 were read read-only from the checkpointer.
- **Existing thread:** "Create a new draft" went to the Builder, which rendered draft turntables of v1, since "draft" is the render tier's name. No path to a new version existed.
- **New thread:**
  1. `import_design` was refused: "package id 'murphy-bed' is already in use".
  2. The owner said "Revise it". The Foreman's model chose a specialist, but the code rule "no piece and no brief → Intake" sent the turn to Intake, which answered with `''` (finish reason `stop`).
  3. The history leaves empty answers out, so the owner saw nothing.
- `revise_package` builds `PackageChanges`, whose validator refuses an empty change set ("state at least one change").

Delete is specified in `studio-chat-polish`:
- the requirement text is in its homeowner-chat, house-file, plan-uploads and studio-ui deltas;
- design §4: "checkpointer first, then the index row and files";
- tasks 1.2, 4.2, 8.2, 8.4 and 9.1.

`uploads` and `thread_tool_settings` cascade from `threads`. `plugin_invocations.thread_id` is `SET NULL`. `render_runs.thread_id` is a plain UUID. `house_file.touch_thread` is already a no-op for a missing row.

Turns run synchronously inside the `POST /turns` and `/resume` requests (`_run` in `app/api/chat.py`). The graph's checkpointer is the LangGraph `PostgresSaver`, which has `delete_thread(thread_id)`. Thread ids in the checkpointer are `chat:<uuid>`.

## Goals / Non-Goals

**Goals:**
- A piece can get a new version without a design change, and from an updated design file.
- "Revise it" about a named piece reaches the Designer.
- The owner never gets a silent turn.
- A conversation can be deleted from the Conversations page.

**Non-Goals:**
- Renaming conversations, generated titles, summaries, streaming, and everything else in `studio-chat-polish`.
- Restoring a deleted conversation.
- Deleting pieces or versions.
- A diff of the imported design against the previous version: the preview shows the new design's summary and names the version it replaces.
- Teaching the Builder to make versions. It keeps its tools; "new version" is routed to the Designer by the Foreman's instructions, and "draft" stays the render tier's word.

## Decisions

1. **`rebuild_piece` is its own tool, not an empty `revise_package`.**
   - The "state at least one change" guard keeps an accidental empty revision from creating a version; a rebuild is a deliberate act with its own card.
   - The tool lives in `plugins/revise_package/` next to `revise_package` (manifest `tools: [revise_package, rebuild_piece]`), so the existing toggle covers both.
   - It reads the latest version's `input.json`, re-validates it with `validated_custom_build`, and runs the design-rule outcome. A design that no longer validates, because the schema grew stricter, is refused by name like any other.
   - It then creates the version with `service.create_version` and records it with `house_file.record_version(..., revised_from=N, changes=["rebuilt unchanged from version N"])`. The thread is bound with `touch_thread`, as `revise_package.run` does.
   - The confirmation subject is `rebuild`.

2. **`import_design_version` reuses the import checks.**
   - It lives in `plugins/design_import/` (manifest `tools: [import_design, import_design_version]`).
   - It shares `_checked`'s upload reading and `parse_import`, with the differences that:
     - the package id must exist (`latest_version` is not `None`);
     - the bound-thread rule becomes "unbound, or bound to this piece".
   - It creates the version like `revise_package.run`, with the change line `imported from <name>, replacing version N` and `revised_from=N`.
   - The confirmation subject is `import_version`.
   - `import_design`'s two refusal strings change to name the version import. Its behaviour is otherwise unchanged.

3. **Routing: a named piece lets the Designer through.**
   - `load_house` already loads `pieces`. It adds `piece_named: bool`: true when the last human message, or the last AI message with text before it, contains a piece's `package_id` (as a word) or its name (case-insensitive).
   - In `foreman()`, the rule "no buildable, no brief → Intake" gains `and not (chosen == "designer" and state.get("piece_named"))`.
   - The model still makes the choice; code only stops overriding it.
   - The image rule (an image turn goes to Intake) still applies after it.
   - `foreman.md` gains a line: a new version, a rebuild or an updated design file for an existing piece is the Designer's.
   - `designer.md` gains when to use `rebuild_piece` and `import_design_version`.
   - **Rejected:** binding the thread to the piece when the import was refused. A refusal must not change state.

4. **Empty answer: one retry, then a fixed reply.**
   - In `specialist_graph.agent`, a reply with no `tool_calls` and empty text (after `_text_of(...).strip()`) triggers a second call. That call gets the same prompt plus a system note: "Your last answer was empty. Answer the owner's message now."
   - A second empty answer is replaced by `AIMessage(EMPTY_REPLY.format(role=...))`, for example "Intake gave no answer. Please rephrase or ask again."
   - Both calls go through `prompt_for` and the usage recorder, so budgets apply. A budget refusal on the retry is the usual refusal message.
   - The Foreman's own structured decision is not affected.

5. **Delete: a per-process running set, checkpointer first.**
   - **Running set:**
     - `app.state.running_turns: set[UUID]`, guarded by a `threading.Lock`.
     - `_run` adds the thread id before `work(...)` and removes it in `finally`.
     - The app runs one process (uvicorn without workers), so the set is complete. With `--reload` a reload starts a fresh process, which also ends the old process's turns.
   - **The route:** `DELETE /chat/threads/{id}`, owner-gated.
     - 404 if the thread row is missing.
     - 409 `turn_running` if its id is in the set.
     - Otherwise `graph.checkpointer.delete_thread(f"chat:{id}")`; any exception gives 503 `MEMORY_DOWN` and nothing else is touched.
     - Then `house_file.delete_thread(session, id)`, which deletes the row (cascading uploads and tool settings) and commits, and then `shutil.rmtree(upload_root / str(id), ignore_errors=True)`.
     - Answers 204.
   - **A turn that starts between the 409 check and the checkpointer delete** is a narrow race in a single-user app. The turn route takes the same lock to check that the row still exists and add itself, and the delete holds the lock across the check and the checkpointer and row deletes.
   - **Frontend:**
     - `api.deleteThread(id)`.
     - On `Conversations.tsx`, a "Delete" button per entry opens an inline confirmation with the text from the spec and Delete/Cancel buttons.
     - On success, the `["threads"]` query is invalidated; on refusal, the message shows beside the entry.
     - The browser's `confirm()` is not used, for testability and consistent styling.

6. **`studio-chat-polish` is narrowed, not rewritten.**
   - Its spec deltas keep their delete sentences, because they will describe what is already true when it archives after this change. The homeowner-chat sentence "A turn running on a thread when it is deleted is not stopped; its result is discarded" is changed to the 409 refusal here.
   - Its tasks lose the delete work:
     - 1.2 keeps title and summary helpers only;
     - 4.2 becomes `PATCH` only;
     - 8.2 drops `deleteThread`;
     - 8.4 keeps start-without-title only;
     - 9.1 drops the delete step.
   - Its proposal's Delete bullet points here.

## Risks / Trade-offs

- **`piece_named` false positives.** A piece id like `bench` matches "bench" in a new wish. The rule only lets the model's Designer choice stand; it never forces the Designer, and the Designer asks before creating anything. Accepted.
- **Re-validation can refuse an old design.** A rebuild of a version made under an older schema may be refused by name. That is the honest outcome, and the owner can revise instead.
- **Delete is permanent.** The confirmation says so, and the pieces stay.
- **The running set is per process.** Several workers would need a database flag. Out of scope: the app runs one process.
- **Changes to an unarchived change.** Editing `studio-chat-polish` means its numbering and scope change. It is not started (0/21), so no work is lost.

## Migration Plan

None: no schema change. Rollback is reverting the code. Deleted conversations stay deleted.

## Open Questions

None.
