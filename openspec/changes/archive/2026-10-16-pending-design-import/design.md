## Context

The Foreman graph is `START → load_house → foreman → <specialist> → END`. Each specialist is a sub-graph (`agent ⇄ tools`); gated tools pause with `interrupt()` and resume inside the same specialist.

Today:
- `_attached()` looks only at the newest owner message, so `design_attached` is true only on the turn that carries the file.
- While no room is confirmed, the Foreman answers a design-file turn with "Which room is this for?". The owner's answer goes to Intake, which confirms the room with the gated `confirm_room` (or `record_brief` / `record_plan`, which also set the thread's room or apartment). The turn then ends with Intake.
- Intake binds no import tool, so its model makes up a reply about the file ("I can't run that import").
- `import_design` already reads any design upload of the same conversation by its id (`_read_upload` checks `upload.thread_id`), so an earlier message's file can be imported without a new upload.

## Goals / Non-Goals

**Goals:**
- The turn that confirms the conversation's first room hands the earlier design file to the Designer, which raises the import preview in that turn.
- The decision is code, not the Foreman model.
- The preview is offered once; a "no" is final until the owner attaches a file again.

**Non-Goals:**
- A room set from the brief form (`PUT /threads/{id}/brief`) outside a chat turn does not hand off. The owner's next turn is routed as today; they attach the file again. Recorded as a known limit.
- Importing as a piece's next version (`import_design_version`): a conversation with a piece never hands off.
- Changing what `import_design` checks or shows.

## Decisions

1. **A hand-off node after Intake, not a Foreman re-route.** `graph.add_edge("intake", END)` becomes `intake → after_intake`. `after_intake` returns `Command(goto="designer" | END)`. It runs after Intake's sub-graph has fully finished, including any resumed `confirm_room` confirmation, so a declined room never hands off. Re-routing through the Foreman was rejected: it would spend a model call and could pick something else.

2. **The pending file is worked out in `load_house`.** While the conversation has no confirmed room or apartment and no piece (no `thread.package_id`, no `thread_pieces` row), `load_house` sets `pending_design = {"upload_id", "name"}`. It is the newest upload of kind `design` named in any owner message's `upload_ids` in this thread. Otherwise it is `None`. `load_house` runs every turn, so the value never leaks into a later turn.

3. **The hand-off condition is read from the database after Intake.** `after_intake` hands off only when all of these hold:
   - `pending_design` is set (so the room was unconfirmed when the turn began);
   - the thread now has a room or an apartment;
   - the thread still has no piece.

   Otherwise it ends the turn. This covers `confirm_room`, `record_brief` and `record_plan` alike, without per-tool flags. Because `pending_design` is only set while no room is confirmed, the hand-off happens once. Later turns see a confirmed room and compute `None`, which gives the "no is final" rule.

4. **The Designer is told by a code-composed note, never a stored message.** `after_intake` updates `specialist="designer"`, `round_count=0` and `handoff_design=pending_design`. It also refreshes `room_confirmed` and the `facts` line, so the Designer does not read "no room confirmed yet". When `handoff_design` is set, the Designer's `agent` appends one note, worded like `with_attachments`:

   > (The owner attached the design file '<neutralised name>' as upload <id> before the room was confirmed; it is now confirmed. Import it with import_design.)

   `load_house` resets `handoff_design` to `None` each turn. The Designer's existing instructions then cover the preview, refusal quoting and package id. The import preview's `interrupt()` resumes in the Designer as for any gated tool.

5. **Intake's instruction gains one line:** when the owner has attached a design file, do not discuss importing it and never say it cannot be imported; once the room is confirmed the app passes it to the Designer. This is defence in depth. Decision 3 does not depend on it.

6. **The dev panel's workflow map treats `after_intake` as internal.** `/admin/workflow` lists every graph node as an agent with a routed model. `after_intake` is added to its internal nodes and drawn as an `intake → designer` hand-off.

## Risks / Trade-offs

- **The Designer's model may not call `import_design`.** This is the same risk as for a file attached after the room is confirmed. The note names the tool and the upload id, so the owner can attach the file again if it fails.
- **Two specialist replies in one turn.** Intake's room reply is followed by the Designer's preview. That is acceptable, and it is why the spec names this as the single exception.
- **Budget.** The Designer call goes through the normal budget node, so a ceiling refusal is reported as today.
- **Brief-form room** is not covered (see Non-Goals).
