## Why

In the conversation "Sideboard / Cabinet" (2026-10-18, 129 messages) the owner was asked the same things again and again, and some answers were lost. The owner gave the hang height four times, typed 1350 mm twice and was asked "Which room is this for?" again after saying "No room for now". Three requests were answered only with "Not verified: no engineering check is available …".

The stored thread shows four causes:
- A piece's place on a wall cannot hold a height.
- Question-card answers do not count as the owner's words.
- Hardware words and the routing model's flag turn ordinary requests into engineering turns.
- A "no" to "Which room is this for?" is not saved.

The summary note and the recent-inputs window held the facts in this thread, so they are not changed here.

## What Changes

- **A wall-hung piece keeps its height (ladder step 2, generator extension).**
  - A piece's wall placement gets an optional `mount_height_mm`: the height of its underside above the floor.
  - Both places that save a piece's position take it: the composition document (`compose_room`) and the saved placement (`ask_placement`, `room_fit`).
  - The composition and room-scene generators lift the piece by it.
  - The overlap and opening checks use the hung height range, so a sideboard can hang above a kommode.
  - The saved placement (wall, distance from the left end, height) is shown to the Designer and the Builder on every turn, so nobody asks for it again.
- **Question-card answers count as the owner's words.**
  - `revise_package` accepts a quote from the answer part of an `ask_owner` result (after "→", or the text the owner wrote instead) since the piece's last version.
  - The question text is never accepted: the model wrote it.
  - A refusal for a missing or uncovered length quotes the owner's sentence that holds it, so the Designer can quote it exactly instead of asking the owner to type it again.
- **An ordinary request is not swallowed by the engineering reply.**
  - Hardware words alone (hanger, hinge, drawer, runner, wall cabinet and the kitchen hardware intents) do not make a message asking for a revision an engineering turn. A load, safety or capacity term still does.
  - When only the routing model flagged a turn and the owner's message holds no engineering term by code, a rejected engineering answer does not stand as the whole reply. The turn is answered once more as an ordinary turn.
  - The code term list gains shelf span and sag wording ("allowable shelf span", "shelf span", "sag", "sagging"), so those questions stay engineering turns without the model's flag.
- **"No room" to the room question is a decline.**
  - When the last reply was "Which room is this for?" and the owner names no room and starts with a no-word ("no", "none", "without", "nein", "keinen"), the conversation's room is saved as declined, as a "no" to the room offer already is.

Out of scope:
- The routing slip where "Please add this to the inspector view" went to the Builder.
- The Designer saying it could not see earlier work.

The uncommitted `room-change-goes-to-designer` change adds the role note that forbids that second claim. Any further routing fix belongs there.

Ladder step: 1 for the agent and routing fixes; 2 (generator extension) for `mount_height_mm`. Agents touched: Foreman (routing, room decline), Designer (revision check, placement), Builder (placement in context, in-room render). The render guard and the bpy allow-list are not affected. Renders still go through the guard at their tier, and the generators stay checked-in headless scripts.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-agents`:
  - A revision's measurement check accepts question-card answers and quotes the owner's sentence when it refuses.
  - New requirements: hardware words alone do not make a revision an engineering turn; a model-only engineering flag never replaces an ordinary answer; a no to the room question is a decline; the saved placement is in the Designer's and Builder's context.
- `room-composition`:
  - New requirement: a wall-hung piece holds its height above the floor and is checked over its hung height range.
- `scene-rendering`:
  - New requirement: a piece's in-room render honours the saved mount height.

## Impact

- `backend/app/agent/measurements.py`: owner texts since the last version include `ask_owner` answers; refusal wording.
- `backend/app/engineering/chat.py`, `backend/app/agent/foreman.py`:
  - engineering term split and new span and sag terms;
  - one ordinary retry on a model-only flag;
  - room decline after `ROOM_QUESTION`;
  - placement line in the notes.
- `backend/app/blender/composition_contract.py`, `backend/app/blender/room_contract.py`, `backend/app/blender/generators/build_room_scene.py`: optional `mount_height_mm`; `_composition.py` already lifts by `base_mm`.
- `backend/plugins/ask_placement/tool.py`, `backend/plugins/room_fit/tool.py`, `backend/plugins/compose_room/tool.py`, `backend/app/packages/placements.py`: take and store the height.
- `backend/app/agent/instructions/designer.md`: use `mount_height_mm` for a hung piece; refuse a height it cannot store by field name.
- Tests: `test_measurements*`, `test_foreman.py`, `test_composition_contract.py`, the room-contract tests, and one `--blender` build of a hung piece.
