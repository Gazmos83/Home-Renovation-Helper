## Why

The end-to-end review of 2026-10-15 found that a new conversation cannot start with a question. "I'd like to build a kitchen counter, how tall should it be?" was answered with "Would you like to view this piece in a room?" and the question itself was never answered. The room offer (`optional-room-question`) fires on every turn of a conversation with no room, unless the turn is a help, price or engineering question. The owner wants to brainstorm first, before attaching a file or asking for a piece.

## What Changes

- **An open question is answered first.** The Foreman's routing decision gains a flag for an open question: the owner asks about or thinks aloud about a piece (usual sizes and heights, materials, ideas, what works) without yet asking for something to be designed, imported, built, rendered, reviewed or priced. Such a turn, in a conversation with no confirmed room that has not declined one, goes to the Designer instead of the room offer.
- **The answer changes nothing.** On an open-question turn the Designer answers in plain words and may look up the guidelines. It has no tool that creates, imports or revises a piece, composes a room, records a brief or a verdict, or asks a form. No piece is created, and no room question is asked in that reply.
- **The room offer comes later.** The next turn that asks for actual work (a wish for a piece, a design file, a build) gets "Would you like to view this piece in a room?" as today.
- **Unchanged:** help questions (Intake), price and product questions (Researcher), engineering questions (Researcher), the code-answered height question, the design-file conflict reply, and every rule once a room is confirmed or declined. A turn carrying a plan, a photo or a design file is never an open question.
- **Assumptions, TODO(user) for review:**
  - the flag is set by the Foreman's routing model; code does not guess from a question mark, so "can you make it 10 cm wider?" is not mistaken for brainstorming;
  - an open question in a conversation that already has a bound piece is routed as today (it is not treated as a separate case).

Ladder: none of the three steps; routing only. Agents touched: the **Foreman** (a new decision flag and a routing rule decided by code) and the **Designer** (a restricted tool set and a note on open-question turns). The **render guard** and the **bpy allow-list** are **not affected**.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `design-agents`: a new requirement that an open question is answered by the Designer before the room offer, with no tool that changes the house file.

## Impact

- `backend/app/agent/foreman.py`:
  - `Decision.open_question`;
  - the router rule ahead of the room offer (after the help rule, before `ROOM_OFFER`);
  - an `open_question_turn` state value;
  - `bound_for` limiting the Designer to `search_guidelines` on such a turn;
  - an `OPEN_QUESTION_NOTE` for the Designer.
- `backend/app/agent/instructions/foreman.md`: when to set `open_question`, with the kitchen-counter example.
- Tests: `tests/test_foreman.py` (routing), `tests/test_instructions.py` (the flag is described).
- Frontend: no change.
- Relation to active changes:
  - `optional-room-question` (browser pass open) owns the room offer this rule comes before;
  - `short-answers-show-maths` formats the Designer's reply (one figure, one sentence) and applies here unchanged.
