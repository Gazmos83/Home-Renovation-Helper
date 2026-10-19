## Why

On 2026-10-17 the owner asked to view the freshly imported `lamellen-kommode` in `Wohnen`. The turn went to the Builder. It cannot place a piece, so it made up a room argument for `render_turntable`. That argument has to be the JSON document `room_fit` returns, and only the Designer has `room_fit`. The Builder then passed the schema error on to the owner: "share the room document (`room_fit` output) for Wohnen". That is internal jargon, and the owner cannot answer it.

The owner wants the missing information asked for as a short series of questions instead, starting with "Where would you like to place the piece? Check out the Room layout."

## What Changes

- **Placement is asked, not explained.** When the owner asks to see the bound, built piece in the conversation's room and the piece has no place in that room yet, the Designer answers. It calls a new `ask_placement` tool, whose questions the application writes, so the model chooses no wording. They are shown one at a time like any question set:
  1. "Where would you like to place the piece? Check out the Room layout." The choices are the room's walls, each as "Wall N (length mm)". A **Room layout** button switches the Workspace to the "Chat and room" layout, where the walls are labelled.
  2. "How far from the left end of that wall should the piece start? (seen facing the wall)", in mm.

  When the answers come back, the same tool runs the room fit itself, so the model never copies a wall number or offset. A refusal, such as a piece too wide or a door in the way, is put to the owner in plain words with the questions again. It is never shown as a field list.
- **A placement is stored.** A successful fit (from `ask_placement` or `room_fit`) saves the placement for that piece version and room. `render_turntable` no longer takes a room document from the model: it takes `in_room: true` and reads the stored placement for the conversation's confirmed room. The fragile copy of a JSON document between two specialists is gone.
- **Showing it follows in the same turn.** After a successful fit on a "show it in the room" turn, the application hands the turn to the Builder. The Builder starts a `draft` still of the piece in the room, through the render guard as always, and the reply gives the estimate. If a placement already exists, the request goes straight to the Builder.
- **No specialist explains internals when something is missing.**
  - A refusal that the owner can resolve is answered by asking for the missing values: through `ask_owner` for Intake and the Designer; for the Builder, by handing back to the Designer through the routing above.
  - Tool names, documents and schema fields never reach the owner. The specialists' instructions say so, and the render tool's refusal texts are written in the owner's words.

Ladder: none of the three steps (no generator or Blender change). Agents:
- **Foreman**: a "view in room" routing rule and the Designer → Builder hand-off, both decided by code;
- **Designer**: the `ask_placement` tool, and `room_fit` storing its placement;
- **Builder**: `render_turntable` takes `in_room` instead of a room document.

The **render guard** is **not affected**: the still is a `draft` through the guard, and `final` still needs a typed yes. The **bpy allow-list** is **not affected**.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `design-agents`: a new requirement for viewing a piece in its room (asking the placement, storing it, the hand-off to a draft still).
- `studio-ui`: a new requirement for the Room layout button on the placement question.
- `homeowner-chat`: a new requirement that missing information is asked for, not explained with internal names.

## Impact

- `backend/plugins/room_fit/tool.py`: store the placement (version folder `placements/<room-slug>.json`). The result text no longer carries the document.
- `backend/plugins/ask_placement/` (new, Designer, not toggleable): composes the two questions from the house-file room, pauses like `ask_owner`, and on the answers runs the fit through the same code as `room_fit`.
- `backend/plugins/render_turntable/tool.py`: `in_room: bool` replaces `room: dict`, and the stored placement is read for the confirmed room. **BREAKING** for the tool's arguments only; no owner-visible break.
- `backend/app/agent/foreman.py`: a `views_in_room` routing flag on the router's decision, the Designer/Builder choice by stored placement, and the hand-off after a successful `room_fit`.
- `backend/app/agent/instructions/{designer,builder,intake}.md`: ask for missing information; never name tools, documents or fields.
- `frontend`: the question set shows a "Room layout" button when the set says so (`frontend/src/routes/Conversation.tsx` question set, `lib/api.ts` type).
- Relation to `optional-room-question`: in a conversation that declined a room, "show it in the room" first asks "Which room is this for?".
