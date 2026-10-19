## Context

See proposal.md (Why). The current state the approach builds on:

- `foreman.py` holds the fixed replies (`ROOM_QUESTION`, `WHICH_PIECE`, `PIECE_HAS_CONVERSATION`). The context node computes `room_confirmed`, `room_named`, `room_asked` (`room_question_asked`: the last reply with text equals `ROOM_QUESTION`), `design_attached` and `pending_design`. The router then:
  1. answers with a fixed reply when `room_confirmed` is false and the turn carries no plan or photo, names no room, and is not an answer to the room question;
  2. hands a pending design file to the Designer after an Intake turn that confirms the room;
  3. sends a bound piece without a room to Intake.
- `create_piece.piece_room` and the design import already accept no room. They return `None` with no refusal, so pieces are recorded unassigned.
- `Thread` has `room_id` (the confirmed room) and no flag for a declined room.

## Goals / Non-Goals

**Goals:**
- No piece is assumed to belong in a room. The room is asked for only after the owner says yes.
- The answer is read by code, so the flow is the same every time and costs no model call.
- The "no" holds for the conversation, so the owner is not asked again.

**Non-Goals:**
- Changing how a room is confirmed once it is given (Intake's `confirm_room` and `record_brief` stay).
- Letting compose or room fit run without a room.
- Asking the question through a form with buttons. The reply stays plain text, as today's fixed questions are.

## Decisions

1. **A thread flag, not a reading of the history.** `threads.room_declined` (boolean, not null, default false) is added by an Alembic migration and set by `house_file.decline_room(session, thread_id)`. Re-reading the history each turn was rejected, because compressed or summarised histories could lose the answer. Confirming a room later does not clear the flag. `room_confirmed` already takes precedence wherever a room exists.

2. **Reading the answer.** In the context node, when the last reply with text equals `ROOM_OFFER`, the owner's message is classified, in this order:
   1. `room_named`, the existing whole-word room or apartment match → `room_answer = "room"`;
   2. the first word, stripped of punctuation and lower-cased, is in `{"yes", "ja", "yeah", "sure", "ok", "okay"}` → `"yes"`;
   3. anything else → `"no"`, which calls `decline_room` in the context node's session before routing.

   `room_asked` keeps meaning "the last reply was `ROOM_QUESTION`", so an answer to "Which room is this for?" goes to Intake as today.

3. **Router order** (fixed replies, after the Researcher, help and design-conflict rules):
   - `piece_has_conversation` → as today;
   - `ambiguous_pieces` → as today;
   - when there is no room, it was not declined, the turn carries no plan or photo and names no room:
     - if `room_answer == "yes"` → `ROOM_QUESTION`;
     - else if `room_asked` → the turn goes on to Intake, as today;
     - else → `ROOM_OFFER`.

   With `room_answer == "no"` the router treats the turn as having a room for routing purposes. When the thread has no piece and `pending_design` is set, it goes to the Designer with `handoff_design = pending_design`, reusing the hand-off the room confirmation uses (`design-agents` "pending design" rule). Otherwise it goes to the model's choice, bounded by the remaining rules.

4. **Room-dependent rules check `room_declined`.**
   - The rule "bound piece has no room, or a room outside the confirmed scope → Intake" is skipped when declined.
   - `build_room_ok` is treated as true when declined and the piece has no room.
   - Compose and room fit keep requiring `room_confirmed`. A compose wish in a declined conversation goes to the Designer only if a room is named, as today.

5. **Instructions.** `foreman.md` and `intake.md` are searched for the quoted room question and the "Designer waits for a room" rule. The wording changes so models never ask for a room themselves after a no. `tests/test_instructions.py` checks that neither file tells the model to insist on a room when the conversation declined one.

## Risks / Trade-offs

- **[A vague answer ("maybe later") counts as no]** → this is the safe direction. Nothing is placed, and the owner can name a room at any time, which still goes to Intake.
- **[Existing conversations]** → the flag defaults to false. Unbound conversations without a room see the new question on their next turn; those with a room are unaffected.
- **[Interplay with `delete-piece`]** → both edit the router's fixed-reply block. The design-conflict reply must stay ahead of the room offer. Whichever lands second merges with that order.

## Migration Plan

One Alembic migration adds `threads.room_declined` with a server default of false. Downgrade drops the column; the code then reads no flag and behaves as "not declined".
