## Why

On the listening wall, version 17 has its door at the top of the cabinet, but the Designer said "the doors cover the bottom two shelves" and refused to deepen shelf 2. The Designer already receives the latest version's stored document in words, but it reads "fronts: 2 doors 746 mm (hinge)" with no position. The generator stacks fronts from the top of a module downward, so the position is fixed by the spec yet never stated. The model fills the gap from the brief ("doors on the bottom"), which is out of date.

## What Changes

- The Designer's summary of the active build's latest version states, for each front, where it sits: its span in millimetres above the module's bottom, whether that is the top, the bottom or between, and which shelves (counted from the bottom) it covers or that it covers none.
- The summary's label tells the model that these positions are what is built, to prefer them over the brief or anything said earlier, and to name the version the figures come from.
- `designer.md` gains the same rule in one line.
- Nothing about versions, the brief, the spec schema or the generators changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `design-agents`: the Designer's summary of the active build's latest version states each front's position and the shelves it covers.

## Impact

- Backend: `app/agent/prompts.py` (`piece_note`), the Designer instructions, and `tests/test_piece_note.py`, `tests/test_instructions.py`.
- No frontend, migration or tool change. The Designer's turns carry a few more words per front.
