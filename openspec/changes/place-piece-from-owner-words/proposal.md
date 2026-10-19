## Why

On 2026-10-19, in the "Sideboard (copy)" conversation, the owner wrote "Please place the sideboard along wall 2 0 mm from wall 3." Two things went wrong:

1. **The questions were asked again.** The Designer called `ask_placement`, which always shows "Where would you like to place the piece? Check out the Room layout." and "How far from the left end of that wall should the piece start?". The tool has no way to take a wall or a distance the owner has already stated.
2. **A render was offered instead of the room view.** After the place was saved, the `view-piece-in-room` hand-off sent the same turn to the Builder for a piece still. Since `rooms-only-renders`, `render_turntable` refuses that call, so the Builder replied "Renders are of rooms, not pieces — … Would you like me to do that now?". The owner had not asked for a render. The next turn ("This needs to go into the inspector view!") went to the Builder again, because a saved place still routes a "view in room" turn there.

The owner wants a stated placement to be taken as given. Placing a piece should end in a room proposal that shows in the room inspector, and a render should come up only when the owner asks for one. This is core behaviour, so it also gets a benchmark: a deterministic end-to-end test, and a live replay against the real models.

## What Changes

- **Stated values are not asked again.** `ask_placement` takes optional `wall`, `distance_mm`, `from_wall` and, for a hung piece, `gap_mm`. Code checks each number the model passes against the owner's latest message. A number that does not appear there is dropped and its question is asked. When the wall and the distance are both stated, nothing is asked: the fit runs straight away. When only one is stated, only the missing question is asked.
  - `from_wall` names the wall the distance is measured from. It must be one of the two walls next to `wall`, and code converts it to the distance from the left end: the next wall is the left end and the previous wall is the right end. A wall that is not next to it is refused in plain words. Example: "wall 2, 0 mm from wall 3" in Wohnen becomes 0 mm from the left end of wall 2.
- **Placing ends in a room proposal, never a render.** A "view in room" turn goes to the Designer whether or not a place is saved. With a saved place, the Designer calls `compose_room` with the new `with_saved_place: true`. Code builds the item list from the room's latest composition and adds the bound piece at its saved place, or moves it there if it is already in the room. The owner's `yes` creates the room version and its headless build, and the room inspector shows it. The Designer → Builder hand-off after `ask_placement` is removed, along with the Builder's "start a draft still in_room" note. **BREAKING** for the `view-piece-in-room` behaviour only. No owner-visible feature is lost: a piece still cannot be rendered on its own.
- **Unapproved version: approve first.** `compose_room` accepts approved piece versions only, and that rule stays. When the saved-place proposal is refused for that reason, the Designer offers approval through a new gated Designer tool, `approve_version`, which asks "Approve version N of <piece>?". A `yes` approves it, exactly as the piece inspector's approve does, and the Designer then calls `compose_room` again.
- **The room proposal speaks your terms** (added 2026-10-19 at the owner's request). The confirmation summary and its table number walls from 1 as the room view does, and give a wall placement's distance from the wall's left end, as the placement questions do. Today they show the 0-based index and the offset from the wall's start corner: "wall 2, 0 mm from wall 3" reads "against wall 1 at 2000 mm". The stored composition, the model's arguments and the refusal texts the Designer reads are unchanged.
- **No render offer unless asked.** Neither the Designer's nor the Builder's reply to a placement or "view in room" turn mentions renders. The Builder's "offer to compose and render the room" stays only for an explicit request to render a piece.
- **Benchmark.**
  - A deterministic end-to-end test with scripted fake models covers the exact sentence. It checks that no question set is shown, that the place is stored as wall 2 at 0 mm from the left end, that the next pause is the `compose_room` confirmation, and that no `render_turntable` call or render wording appears.
  - A new pytest marker `benchmark`, skipped unless `--benchmark` is passed, replays the same sentence through the real routed Foreman and Designer models on a seeded Wohnen and sideboard. It asserts the same outcomes. It spends a few cents per run on OpenRouter.

Ladder: none of the three steps (no schema, generator or Blender change). Agents:
- **Foreman**: "view in room" always goes to the Designer; the Builder hand-off is removed.
- **Designer**: `ask_placement` arguments, `compose_room`'s `with_saved_place`, the new `approve_version`, and the instructions.
- **Builder**: the "draft still in_room" note is removed.

The **render guard** is **not affected**: nothing new renders, and fewer render calls are made. The **bpy allow-list** is **not affected**.

## Capabilities

### New Capabilities

- `agent-benchmark`: live replays of core owner sentences through the real routed models, opted into with `--benchmark`, starting with this placement case.

### Modified Capabilities

- `design-agents`: "A piece is viewed in its room after the owner places it" (from `view-piece-in-room`) changes. Stated values are taken, a saved place leads to a room proposal and not a Builder still, and the approve-first path is added. `compose_room` gains `with_saved_place`.

## Impact

- `backend/plugins/ask_placement/tool.py`: new optional arguments, the owner-words check, the `from_wall` conversion, a preview that returns `None` (no pause) or only the missing questions, and `run` merging stated values with answers. Tests in `tests/test_ask_placement.py`.
- `backend/app/compositions.py`: the summary line and table placement in owner terms (wall N, mm from the left end), with tests in `tests/test_compose_room.py`.
- `backend/plugins/compose_room/tool.py` and `backend/app/compositions.py`: `with_saved_place` (with `items` then omitted) and the item list built from the latest room composition plus the saved placement.
- `backend/plugins/approve_version/` (new, Designer, not toggleable): a gated tool calling `house_file.approve_version`.
- `backend/app/agent/foreman.py`: `views` routes to the Designer only. `after_designer`'s Builder hand-off, the Builder's in-room note and the `placement_saved`/`placement_ready` routing use are removed. The Designer's note is reworded.
- `backend/app/agent/instructions/designer.md` and `builder.md`, with `tests/test_instructions.py`.
- `tests/test_view_in_room.py` is rewritten to the new flow. New file `tests/test_place_from_owner_words.py` (deterministic). New file `tests/test_benchmark_agents.py` (live, `benchmark` marker), and the `--benchmark` option in `backend/conftest.py`.
- Order: apply after `view-piece-in-room` and `rooms-only-renders` are archived (both are waiting only on browser passes). This change modifies the requirement `view-piece-in-room` adds.
