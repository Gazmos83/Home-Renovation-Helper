## Context

See proposal.md (Why). The current state the approach builds on:

- **Routing** (`foreman.py`, `foreman()`): the model returns `Decision` with `specialist` and `composes_room`. Code sets `room_wish = composes_room and room_confirmed` and upgrades only `intake` to `designer`. A turn the model gives to the Builder stays with the Builder whenever `composition_ready` (a built composition) makes it "buildable".
- **Tool refusal** (`tools_node`): a call to a tool the specialist has not bound returns `tool_refusal(...)` ("`compose_room` belongs to the Designer, not to you. Nothing was done or saved."). The specialist then writes its own reply around it.
- **Existing hand-offs:** after Intake confirms a room, `after_intake` sends a pending design file to the Designer with a note. After a Designer round that saved a placement on a `views_in_room` turn, `after_designer` sends the turn to the Builder.
- **History:** stored `AIMessage`s carry no speaker, so a specialist cannot tell its own earlier replies from another's.
- **Composition note:** `house_file.compositions()` reads the latest version's `input.json` and `placed_items()` keeps `id`, `type`, name, `room`, `placement`, `layer`. The same document's `resolved.items` holds `size_mm {w,d,h}`, `centre_mm [x,y]` and `rotation_deg` per item id, and is dropped.

## Goals / Non-Goals

**Goals:**
- A request to change a composed room reaches the Designer on the turn it is made.
- The owner never reads about agents handing work to each other; they read whether the room is being composed.
- The Designer has every placed item's size and place without asking.

**Non-Goals:**
- Showing which specialist answered in the homeowner chat (it stays "Foreman").
- A generic hand-off for every foreign tool. Only `compose_room` is handed over; other foreign calls are refused as today.
- Converting "N mm from wall k" into coordinates in code. The Designer computes it from the note, with the `calc` block that short-answers-show-maths already requires.

## Decisions

1. **Builder → Designer when composing.** In `foreman()`, extend the `room_wish` rule: when `room_wish` and `chosen` is `intake` **or `builder`**, choose `designer`. A render request leaves `composes_room` false, so rendering a composition still reaches the Builder. `views_in_room` keeps precedence, as it is decided after. `foreman.md` adds: "Moving, adding, removing or re-placing anything in a composed room is composing it (`composes_room` true), even right after a build or render."

2. **`compose_room` hand-off.** In `tools_node`, when the call is `compose_room` and the specialist is not the Designer, nothing runs. The node sets `handoff_compose: true` in state and ends the specialist's round. A new conditional step after each non-Designer specialist (the same pattern as `after_intake`) routes to `designer` when `handoff_compose` is set:
   - It removes that specialist's last `AIMessage`, its text and the tool call, and the synthetic tool result from the messages it adds, so the owner never sees "I'll pass this to the Designer".
   - It clears the flag.
   - It adds a Designer note: "(The owner's latest messages ask to change this room. Restate the change list, or call `compose_room` if the owner has already said the list is complete.)"

   The Designer then follows its existing change-list rule. This happens at most once per turn. The Designer has `compose_room` bound, so it cannot loop. If the `compose_room` plugin is switched off for the service, the hand-off does not happen and today's refusal stands.

   *Alternative considered:* routing alone (decision 1). Rejected as the only fix, because the router is a model and will sometimes misroute again. The hand-off is the code guarantee.

3. **Role note.** `specialist_graph.agent` appends a fixed note: "You are {label} on this turn. Earlier assistant replies in this conversation may have been written by other specialists; their limits are not yours. Never offer to pass a request to another specialist and never say you cannot see another specialist's work." It is composed by code before the untrusted-content guard, as other notes are.

4. **Sizes and places in the note.** `placed_items(session, document)` merges `document["resolved"]["items"]` by `id` into each entry: `size_mm`, `centre_mm` and `rotation_deg`. A document without `resolved`, or an item missing from it, keeps today's entry. `composition_note` renders, for example: `listening-wall (piece: listening-wall v18) on wall 1 (index 0) at offset 497 mm; 2206 × 562 × 2238 mm, centre (1600, 281) mm, rotated 0°`. Coordinates are explained once in `COMPOSITION_PREAMBLE`: "Centres are room coordinates in mm from the room's first corner; w runs along the wall, d away from it." `designer.md` adds: "Take every placed item's size and position from the composition note; never ask the owner for them. A piece's depth in the room is the note's d, not a cut-list part."

## Risks / Trade-offs

- **Longer prompt:** about 20 tokens per placed item; Wohnen's seven items add about 150. Acceptable against the Designer's roughly 24k-token prompt.
- **Dropping the specialist's message:** if the Builder also did real work in that round (for example started a render) and then called `compose_room`, its text is lost. Mitigation: the hand-off happens only when `compose_room` is the round's only tool call. Otherwise today's refusal is kept.
- **Stale centres:** the note shows the *latest* version, which may differ from the approved one. It already says which version is approved, so this is unchanged.
