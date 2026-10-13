## Why

Two owner reports from 2026-10-13:

1. An engineering reply shows a long code-rendered block: "NOT VERIFIED. Numerical engineering calculation is not implemented…", the "preliminary design advice" line, "engineering lookup is switched off", a list of seven missing inputs and a legal note. The owner does not want that block in the chat; the status should be summarised in 20 words or fewer.
2. "Can you please put v18 to the right of the door of wall 1, 30 cm away from wall 2?" was answered with that block instead of placing the piece. The code matcher (`engineering_intent`) does not match the message; the Foreman's routing model set `engineering_question` (most likely for "wall"), and the model flag alone sends a turn down the engineering path.

## What Changes

- The engineering status block is replaced by one fixed sentence of at most 20 words: "Not verified: no engineering check is available, so load capacity, fixings and safety are unconfirmed." It replaces the not-implemented line, the preliminary-advice line, the lookup-off line, the missing-inputs list and the legal note, on both the valid and the rejected path.
- Evidence the specialist selected from this turn's tools (citations, property values, conflicts, code-generated reports, metadata links) is still shown below that sentence when present; those lines are data the owner asked for, not boilerplate.
- A placement request — put/place/move/position a piece relative to a wall, door, window or corner, or at a stated distance — is not an engineering turn when the code matcher finds no engineering term, whatever the routing model flagged. It is routed like any other room or piece request.
- **Behaviour change made explicit:** the reply no longer lists missing inputs or the legal note. The kitchen-engineering requirement to name missing inputs is relaxed to "reports NOT VERIFIED"; `missing_inputs()` stays for the model-facing request history and tests.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `homeowner-chat`: the engineering status is one short sentence; a placement request is not routed to the engineering path by the model flag alone.
- `kitchen-engineering`: kitchen replies report NOT VERIFIED without listing missing inputs in the chat.

## Impact

- Backend: `app/engineering/chat.py` (`render_answer`, a short-status constant, a placement matcher), `app/agent/foreman.py` (the `engineering` decision), tests in `test_engineering_chat.py`, `test_kitchen_engineering.py`, and a Foreman routing test.
- No frontend, migration or prompt change.
- Trade-off: the owner no longer sees which inputs are missing; the Designer or Researcher can still ask for a specific figure in prose on a later turn.
