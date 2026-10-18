## Why

End-to-end test of 2026-10-18 (conversation `8aa30dca`, room `Wohnen`, composition v13 just created): the owner asked "Please move the table 500 mm away from wall 1 and 600 mm away from wall 5." The room was never changed and the owner got no useful answer.

- **The Foreman gave the turn to the Builder.** The Designer's previous reply ended with "The Builder can render it once it's built." The code only moves a room request to the Designer when the model picked Intake, not when it picked the Builder.
- **The Builder acted as a go-between.** For three turns it gathered the change list, promised to "pass it to the Designer", then called `compose_room` itself. The call was refused ("belongs to the Designer"), and its arguments still held the table's old position. The owner does not need to hear about the exchange between agents, only whether the room is being composed.
- **The Designer took over the Builder's refusals.** The next two turns did reach the Designer. Every earlier reply in the history looks like one assistant voice, so the Designer carried on in the Builder's role: "moving furniture is done by the Designer, not by me", "I can't see the Designer's activity from here".
- **The Designer does not know the other items' sizes or exact positions.** Its house note lists each placed item by name with only its wall and offset. Sizes, centres and rotations are stored in the version's resolved document but never reach the prompt. So the Designer asked the owner for the listening wall's width (2206 mm, already stored). It took the depth from the cut list (388 mm) rather than the placed depth (562 mm), so the table would have been placed 174 mm too close to the cabinet. It also asked the owner to confirm positions the app already holds.

Composition approval played no part: routing and `compose_room` do not depend on which composition version is approved.

## What Changes

- **Routing.** While the conversation has a confirmed room or apartment with a composition, a turn the Foreman flags `composes_room` goes to the Designer, also when the model picked the Builder. The Foreman's instructions say that moving, adding, removing or re-placing an item in a composed room is composing it.
- **`compose_room` from another specialist is handed to the Designer.** When a specialist other than the Designer calls `compose_room`, nothing runs. The application continues the same turn in the Designer, as the existing Intake → Designer hand-off does. The other specialist's text in that reply is dropped. The owner sees only the Designer's answer: the `compose_room` summary waiting for "yes", its change-list question, or a plain statement that the room was not changed and why.
- **No relaying.** No specialist offers to pass a request to another specialist or says it cannot see another specialist's work. A non-Designer asked to change a room says in one sentence that the room has not been changed yet.
- **Each specialist knows who it is on this turn.** A fixed note tells it which specialist it is, and that earlier assistant replies in the thread may come from other specialists, whose limits are not its own.
- **Placed items carry their size and place.** The composition house note lists every item of the latest version with its size (w × d × h mm), its centre in room coordinates and its rotation, taken from the version's resolved document, beside today's wall and offset. The Designer instructions say to take sizes and positions of placed items from that note and never ask the owner for them.

No breaking change: no schema, migration, API or frontend change. Ladder step 1 behaviour only (routing, prompts, notes). Render guard and `bpy` allow-list: not affected.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `design-agents`: routing sends a change to a composed room to the Designer even when the model picked the Builder; a `compose_room` call by another specialist hands the turn to the Designer instead of returning a refusal; specialists are told their own role and never relay.
- `house-file`: the composition house note lists each placed item's size, centre and rotation.

## Impact

- `backend/app/agent/foreman.py`: the Builder → Designer override for `composes_room`; the `compose_room` hand-off in `tools_node` and a routing step after a specialist; the per-turn role note.
- `backend/app/agent/house_file.py` (`placed_items`) and `backend/app/agent/prompts.py` (`composition_note`): carry and show the resolved size, centre and rotation.
- `backend/app/agent/instructions/foreman.md`, `designer.md`, `builder.md` (and the shared hand-off wording in the others): what counts as composing, take sizes from the note, no relaying.
- Tests: `tests/test_foreman.py`, `tests/test_prompts.py`, `tests/test_house_file.py`, `tests/test_instructions.py`.
