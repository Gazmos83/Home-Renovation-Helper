## Context

See proposal.md (Why). Current state in `backend/app/agent/foreman.py`:
- `Decision` (`:223`) carries `composes_room`, `engineering_question`, `requests_revision`, `asks_help` and `views_in_room`, all set by the Foreman's routing model.
- The `foreman` node (`:987`) runs, in order: the design-file conflict reply, the routing model call, the code height reply (`engineering_chat.height_question`), the engineering re-route to the Researcher or Designer, the help rule to Intake, then the fixed questions: `PIECE_HAS_CONVERSATION`, `WHICH_PIECE`, and the room offer or room question when `room_confirmed` and `room_declined` are false and the turn carries no image, names no room and does not answer the room question (`:1053-1067`).
- "I'd like to build a kitchen counter, how tall should it be?" matches none of `_ENGINEERING` (`counter` is not `countertop`), so the room offer is the reply.
- `bound_for` (in `specialist_graph`) already filters tools by state (`engineering_turn`).

## Goals / Non-Goals

**Goals:**
- A question asked before any request is answered, in the same turn, without a room.
- The answer cannot change the house file.
- The existing room offer stays for real requests.

**Non-Goals:**
- Answering open questions with a code-composed reply.
- Changing the order of the help, price, engineering or design-conflict rules.
- Treating open questions differently once a room is confirmed or declined: the other rules already route those to a specialist.

## Decisions

1. **A routing-model flag, like `asks_help`.** `Decision.open_question: bool = False`, described as "true when the owner asks a question or thinks aloud about a piece (sizes, heights, materials, ideas) without asking yet for anything to be designed, imported, built, rendered, reviewed or priced". A code heuristic (a trailing question mark, question words) was rejected: "can you make it wider?" is a request, and the owner asked for a request to keep its room offer.

2. **Rule position.** Directly after the help rule and before the fixed questions:
   - `open_question` is true, `engineering` is false, `chosen != "researcher"`;
   - no `image_attached`, no `design_attached`;
   - `room_confirmed` and `room_declined` are false.
   Then the turn goes to `designer` with `open_question_turn: True` (and `engineering_turn: False`), skipping the fixed questions and the "no brief → Intake" rule. With a room confirmed or declined, the flag is ignored and routing goes on as today.

3. **Restricted Designer.** In `bound_for`, when `state["open_question_turn"]` is true, the Designer gets only `search_guidelines`. The agent node adds `OPEN_QUESTION_NOTE`: "(The owner is asking a question before any piece exists. Answer it in plain words, citing the guidelines when they help. Do not create, import or revise a piece and do not ask which room it is for.)". `designer_note` (the templates) is not added on such a turn. `open_question_turn` is reset to false by the router on every other route, like `engineering_turn`.

4. **No state left behind.** The reply is an ordinary Designer reply, so the next turn's last reply is not `ROOM_OFFER`; `room_answer` stays unset and the room offer comes on the first real request.

## Risks / Trade-offs

- [The cheap routing model marks a request as an open question] → the Designer cannot create anything on that turn, so the worst case is one extra turn. The instruction lists both examples (the kitchen-counter question and "can you design a shoe bench?").
- [The model misses an open question] → the room offer appears, as today; no regression.
