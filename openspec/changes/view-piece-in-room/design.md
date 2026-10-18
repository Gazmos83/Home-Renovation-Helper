## Context

See proposal.md (Why). The current state the approach builds on:

- **`room_fit`** (Designer) takes `room_name`, `package_id`, `version`, `wall` (0-based) and `offset_mm` (along the wall from its start corner). It checks the fit and returns text ending in `Room document (pass it as room to render_turntable): {json}`. The model is expected to copy that JSON into `render_turntable(room=…)` (Builder). The two tools belong to different specialists, so the copy only works when both run in the same thread history, and the model can invent the document, as it did on 2026-10-17.
- **`render_turntable`** builds the scene from `service.room_scene_document(folder, kind, room)`. Its refusal texts are raw validation messages.
- **`ask_owner`** returns `Questions(questions=[{text, unit, choices}])` from `preview`, pauses the turn, and receives `ctx.answer` in `run`. The frontend shows the set one question at a time, so it already forms "a series of questions".
- **The Workspace room pane** ("Chat and room" layout) shows the room composition's 3D view, with "wall N: length mm" labels behind its dimensions switch. Wohnen has a composition.
- **Handing a turn from one specialist to another is already done once:** after Intake confirms a room, the turn goes on to the Designer for a pending design. The Foreman decides it in code.

## Goals / Non-Goals

**Goals:**
- No model copies a placement or room document between tools.
- The owner is asked in two short questions, with a pointer to the labelled walls.
- "Show it in the room" ends in a running draft still in the same turn once a place is known.

**Non-Goals:**
- Choosing which way the piece faces. It stands against the wall, facing into the room, as `room_fit` places it today.
- Placing a piece in a room composition. Composing stays the Designer's `compose_room` flow, for approved versions.
- A 2D floor plan for rooms without a 3D view.

## Decisions

1. **One placement store, written by the fit.** Factor the fit logic of `room_fit` into `room_fit.fit(session, root, room, package_id, version, wall, offset_mm)`. It returns either a plain refusal or the placement and the room-scene document. On success it writes `<version folder>/placements/<room-slug>.json` (placement, scene document, wall, offset, and the left-end distance as asked). The file sits in the version folder, so it is deleted with the version and never outlives a rebuild of a different version. `room_fit`'s result text drops the "pass it as room" document and says "Placement saved for <room>".

2. **`ask_placement` (Designer, not toggleable).** Its arguments are none beyond the bound piece, taken from `ctx` (session, project and scope come from the context, never from the model).
   - **`preview`** reads the conversation's confirmed room. It returns `Questions` with the two fixed texts, the wall choices "Wall N (L mm)" for walls 1–8, unit mm on the second question, and `layout: "room"` on the set.
   - **`run`** maps the chosen wall label, or a typed number, to an index. It converts the left-end distance to `offset_mm`: corners run counter-clockwise in plan, so seen from inside facing wall N its left end is the wall's end corner, and `offset_mm = length − distance − piece width`. This is checked once against the room contract's orientation in a test, and flipped if the contract runs clockwise. It then calls `fit` and returns either "Placement saved for <room>: wall N, D mm from the left end" or the plain refusal, which the Designer instruction tells the model to say and ask again.
   - A declined set returns the owner's words, as `ask_owner` does.

3. **`render_turntable(in_room: bool = False)`.** The `room: dict` argument is removed. With `in_room`, the tool loads `placements/<confirmed-room-slug>.json` of the target version, where the confirmed room comes from `ctx`. Missing → "This piece has no place in <room> yet; the Designer will ask where it goes." `in_room` with a composition or a shell target is refused as `room` is today.

4. **Routing.** The router's decision model gains `views_in_room: bool` ("the owner wants to see the bound piece in its room"), as `composes_room` exists today. In code:
   - when it is true, the piece has a successful build, and the conversation has a confirmed room: the Builder when a placement exists, else the Designer;
   - in a conversation that declined a room (optional-room-question): `ROOM_QUESTION`.

   After a Designer round in which `ask_placement` returned "Placement saved" on a `views_in_room` turn, the graph goes on to the Builder with a system note to start a `draft` still `in_room`. This mirrors the Intake → Designer hand-off: same mechanism, a new trigger.

5. **The frontend.** The question set's API type gains an optional `layout: "room" | null`. `Conversation.tsx` shows a "Room layout" button beside the first question when it is set. The button calls the Workspace's layout setter ("chat-room"; on narrow screens the room pane tab) and leaves the set's local answers untouched.

6. **Instructions.** `designer.md`, `builder.md` and `intake.md` each gain one line. Ask for what is missing with the question tool (or, for the Builder, say in one sentence that the Designer will ask). Never name a tool, a document, a field or a JSON key. `tests/test_instructions.py` asserts the line and that `builder.md` no longer mentions passing a room document.

## Risks / Trade-offs

- **[Left/right confusion]** → the question says "seen facing the wall". The conversion is pinned by a test on a known polygon. The room pane labels let the owner check.
- **[More than 8 walls]** → the choices list the first eight and the free answer takes any wall number. This is rare in practice.
- **[Old threads whose history holds a room document]** → `render_turntable` no longer accepts it. A model that tries gets the plain refusal and the routing asks for a placement.
- **[A stored placement goes stale after a room is re-measured]** → `render_turntable` re-runs `fit` from the stored wall and distance before rendering. A refusal then routes back to the Designer's questions.

## Migration Plan

No schema change. Placements are files written from now on. Rollback restores the `room` argument and removes the tool; stored placement files are ignored.
