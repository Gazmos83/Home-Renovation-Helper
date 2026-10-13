## Context

The note is plain text, kept per build (`thread_pieces.summary`) or per thread (`threads.summary`). The panel (`DecisionsNote.tsx`) reads it as rows (a `**Topic:**` label or the nearest `##` heading is the topic) and saves the whole note through `PUT /chat/threads/{id}/note`, which neutralises the text and calls `house_file.write_owner_summary`. Specialists own tools; the Foreman routes and has none. Gated tools pause through `Tool.preview` and `interrupt()` in `foreman.py`; `revise_package` is the pattern. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- One chat tool that changes a single row with the panel's exact rules and save path.
- A shown before/after and a typed "yes" before any write.

**Non-Goals:**
- No automatic recording of decisions as they are made, and no change to when the note is compressed.
- No change to the panel's own controls, other than the pre-filled add row or to the refresh prompt.
- No multi-row or free-text rewrite from the chat (the model could not be checked against the rules).

## Decisions

1. **Designer holds the tool, not the Foreman.** The Foreman has no tools and only routes, so the owner's request reaches the tool through the Designer, who already discusses pieces and decisions. Alternative: give the Foreman a tool, which breaks "specialists own tools". TODO(user): confirm the Designer, or name another agent.
2. **Confirmation before every write, including add and change.** Deleting loses text, and the model may mishear a request, so the owner sees the row before and after. Alternative: confirm deletes only, which hides a wrong edit until the next read.
3. **Row rules in Python, mirroring the panel.** A small module `app/agent/decisions_note.py` parses rows, replaces, appends and deletes a line exactly as `noteRows`, `replaceRow`, `appendRow` and `deleteRow` do in the SPA. Tests run the same cases on both so they cannot drift. Alternative: send the whole new note from the model, which would let it rewrite lines the owner did not mention.
4. **Rows are named, not numbered by the model.** The call carries `topic` (and optional `position` among rows with that topic). The tool resolves the line itself, so a stale line number cannot hit the wrong row. An ambiguous name is refused in `preview`, before the pause, On a resume the preview is replayed, and `run` then re-resolves the row from the current note in the same transaction as the write, so it never acts on a stale line number and refuses if the row no longer exists.
5. **Same save as the panel.** The write goes through one shared function that neutralises, enforces the 8000-character limit and non-empty rule and calls `write_owner_summary`; the route and the tool both use it. Scope (thread and build) comes from `ToolContext`.
6. **Panel refresh by invalidation.** When a turn ends, `Conversation.tsx` invalidates the `["conversation-note", threadId]` query, so no new route or push is needed.

7. **Explicit request only, enforced twice.** `designer.md` tells the model to call the tool only when the owner's message asks for the change, and to offer rather than act. The confirmation is the code-enforced backstop: the tool cannot write without the owner's "yes", so an unprompted call at worst shows a prompt the owner declines. Alternative: no code check beyond the confirmation, which is what is chosen; detecting "explicit" in code from the message text would be fragile.
8. **"Add to decisions" is a UI path with one summary call, not a tool.** The button calls a summary route that uses the existing side-call slot (the Foreman's, as for titles and summaries; `chat.decision`), through the budget node, with the message wrapped in the injection delimiters. Thread and build come from the session; the route returns only `{topic, decision}` (Pydantic-validated, decision capped at 2000 characters). The panel opens, if closed, with that row pre-filled; the owner edits and saves it, so no confirmation step is needed and saving makes no model call. A failure or refused call opens an empty row with a message, never the full text. Alternatives: rule-based truncation (crude) and reusing "Compress now" (compresses the note, not the message).

## Risks / Trade-offs

- [Python and TypeScript row rules drift] → shared test cases on both sides, one table of inputs and expected notes.
- [The model acts without being asked] → the instruction, and the confirmation that needs a "yes".
- [The model proposes the wrong row] → the owner sees the row before and after and must answer "yes".
- [A later automatic refresh rewrites the owner's chat edit] → the same as a panel edit: the note is marked as the owner's and kept as the base of the refresh.
- [Prompt injection through the note text] → rows are shown inside the existing untrusted-content delimiters and the tool never executes row text.

- [A token ceiling refuses the summary call] → the row opens empty with a plain-words message; the owner can still type a decision.

## Open Questions

- The panel's save keeps only the owner mark, not who edited. Whether a chat edit should be labelled differently from a table edit does not change the specs or tasks and can wait.
