## Context

See proposal.md for the why. Today:

- The checkpointer keeps one memory per conversation (`chat:{thread_id}`, `app/agent/chat.py` `checkpoint_thread`). The brief lives in that state (`ChatState.brief`).
- `load_house` in `app/agent/foreman.py` loads every room, preference, piece, apartment, composition, ready library model and open generator-extension request, and `house_note` / `composition_note` in `app/agent/prompts.py` print all of it. The Foreman, Intake and the Designer get the house note; the Designer and the Builder get the composition note.
- `threads.package_id` is the bound piece. `create_and_record` (`plugins/create_piece/tool.py`) and `record_next` (`plugins/revise_package/tool.py`) set it through `house_file.touch_thread`. The design import uses both functions.
- `pieces.room_id` already exists (migration 0002) and `create_and_record` fills it from `brief["room"]` when that room is stored. Nothing else sets it, so most pieces have no room.
- `generator_extension_requests` (`app/db/models.py`) has a nullable `package_id` and no conversation column. `record_unknown_fields` (`app/agent/tools/base.py`) records them through `house_file.record_extension_request`.
- One summary per thread: `threads.summary` / `summary_through`, read and written by `app/agent/summaries.py` through `house_file.read_summary` / `write_summary`.
- `piece_named` matches any house-file piece by id or name and returns a bool.
- `Room.name` is unique and rooms have no owner or project link. That stays.

## Goals / Non-Goals

**Goals:**
- A conversation's room is confirmed in that conversation, and the context is scoped to it and its builds.
- Fewer tokens per turn in a house file with many pieces; the prompt does not grow with the house file.
- Every rule is enforced in code. Instruction files stay as they are, except one tool name in Intake's header.

**Non-Goals:**
- No Project entity above conversations. A conversation is the project.
- No change to the Studio conversation layout, the project panel, render notices, the Reviewer or hardware (other changes own those). The project panel does not show the room in this change.
- No change to how rooms are measured or validated, to `room_fit`, or to the render guard and the bpy allow-list.
- No per-conversation copy of room data. The house file stays the one long-term store.

## Decisions

### 1. Data model: thread scope columns and a `thread_pieces` table

Migration `0014_conversation_rooms`:
- `threads.room_id` (FK `rooms.id`, `ON DELETE SET NULL`) and `threads.apartment_id` (FK `apartments.id`, `ON DELETE SET NULL`), with a check that at most one is set. This is the conversation's confirmed scope.
- New table `thread_pieces`: `thread_id` (FK `threads.id`, `ON DELETE CASCADE`), `package_id` (string, no FK, like `threads.package_id`, because a folder-only package can be named before it has a `pieces` row), `summary`, `summary_through`, `added_at`; primary key `(thread_id, package_id)`.
- `generator_extension_requests.thread_id` (FK `threads.id`, `ON DELETE SET NULL`, nullable), declared like `model_usage.thread_id` with a named constraint. A deleted conversation keeps its requests.
- `threads.package_id` stays and means the active build. `threads.summary` stays and holds the summary for exchanges with no active build.
- Backfill: every thread with a `package_id` gets a `thread_pieces` row for it, and its `summary` / `summary_through` move to that row (then cleared on the thread). No thread gets a room. `pieces.room_id` is left as it is: pieces with no room stay unassigned. Existing requests keep `thread_id` empty.

*Alternative:* a JSONB list of builds on `threads`. Rejected: the summary per build needs its own columns, and a table cascades cleanly on delete.

### 2. Confirming the room: `confirm_room` in the `intake` plugin

A new gated tool `confirm_room(room | apartment, package_id?)` in `plugins/intake/tool.py`, listed in `plugins/intake/manifest.yaml` and in the header of `app/agent/instructions/intake.md`. Only the tool name is added to the header; the tool's description lives in code. The preview reads the stored room (or the apartment's rooms) and shows its measurements. The run sets `threads.room_id` or `apartment_id` (clearing the other) and, with a `package_id` that is one of the conversation's builds, sets `pieces.room_id`.

`record_brief` on `yes` with a room name also sets the thread's room. Its preview for a stored room now prints the stored measurements instead of "as already in the house file". `record_plan` on `yes` sets the thread's apartment. A brief that names no room gets the conversation's confirmed room name filled in by `_brief` when the thread has one.

*Alternative:* confirm the room only through `record_brief`. Rejected: switching rooms or moving a build would then need a whole new brief.

### 3. The room gate and the ambiguity check in the Foreman node

Both are code rules in the `foreman` node, after the model's decision, in the order the spec lists. The design-file rule (`design_attached` sends the turn to the Designer) moves after the room gate: with no confirmed room a design-file turn gets the room question like other design work, and nothing is imported. The owner attaches the file again once the room is confirmed. The price-question → Researcher and plan/photo/named-room → Intake exceptions stay.

The two fixed replies are constants in `foreman.py`:
- `ROOM_QUESTION = "Which room is this for?"`
- `WHICH_PIECE = "Which piece do you mean: {names}?"`

The node returns `Command(update={"messages": [AIMessage(text)], "specialist": ""}, goto=END)`, the same shape as the budget refusal. The routing call is still made first, because the Researcher exception needs its decision; a separate pre-check would save that call but duplicate the routing.

"Answers the room question" means the last AI message with text is exactly `ROOM_QUESTION`. "Names a room" uses a new `room_named(messages, rooms, apartments)` that matches whole words, case-insensitive, like `piece_named`.

`piece_named` is changed to return the matched pieces, not a bool. `load_house` uses it: two or more matches among the conversation's builds set `ambiguous_pieces`; exactly one match that is not the active build switches `threads.package_id` and adds a `thread_pieces` row before the context is built. A match outside the conversation joins it the same way. This write happens at the start of the turn, so it is the only write `load_house` makes.

*Alternative:* tell the Foreman in its instructions to ask. Rejected: the owner wants short prompts, and a model can skip the rule.

### 4. Scoped loading

`load_house` builds a scope first: the thread's confirmed room (or apartment and its rooms), its builds, its active build. Then:
- rooms: only the confirmed room, or the apartment's rooms; nothing when none is confirmed;
- apartments: only the confirmed one;
- pieces: the active build in full, the other builds as one line each (new `house_note` argument `other_builds`), nothing else;
- generator-extension requests: only open ones whose `package_id` is one of the builds or whose `thread_id` is this conversation (new `house_file.open_extension_requests(session, package_ids=..., thread_id=...)`). `record_unknown_fields` passes `ctx.thread_id` to `record_extension_request`, so a request made before any piece exists still reaches its conversation. Older requests with neither stay listed in the house file and appear in no prompt;
- compositions: only those whose scope is the confirmed room, or the confirmed apartment and its rooms. The ready model library list is unchanged;
- the `facts` line names the confirmed room or apartment, or says none is confirmed;
- `compose_ready` counts approved versions of pieces in the confirmed scope only.

`house_note` and `composition_note` keep their format and only receive less. The Foreman still gets the house note, now scoped.

### 5. One summary per build

`house_file.read_summary(session, thread_id, package_id)` and `write_summary(..., package_id, ...)` read and write the `thread_pieces` row when `package_id` is set, the `threads` columns otherwise. `summaries.summarizer(engine, thread_id, package_id, call)` passes the active build through; `foreman.py` gives it `state["package_id"]`. `SUMMARY_INSTRUCTION` gains one sentence asking to keep only what concerns the named piece when one is named; the piece id is passed in the human message, never in the system text. The reuse rule (`summary_through` among the dropped ids) is unchanged, so a stale build summary is refreshed from the newly dropped messages only.

*Alternative:* split the dropped messages by build. Rejected: messages carry no build tag, and guessing one is the hallucination the owner wants gone.

### 6. Piece room on create, and the attach routes

A helper in `plugins/create_piece/tool.py` picks the room: the brief's room when stored, else the thread's confirmed room. With an apartment scope and no room of that apartment in the brief, `create_piece`'s preview refuses with the question. The design import uses the same helper: it only runs after the room gate, so the piece is recorded in the conversation's confirmed room, and with an apartment scope its preview refuses with the same question.

Routes: `GET /rooms` (names only, owner-gated, new `app/api/rooms.py`); `PUT /packages/{package_id}/room` with `{"room": name | null}` in `app/api/packages.py`; `GET /packages` entries gain `room` (name or null). The Pieces page (`frontend/src/routes/Pieces.tsx`) shows the room and a select.

### 7. Docs

CLAUDE.md §9a gets one sentence: rooms are confirmed per conversation and the prompt carries only the conversation's room and builds; the house file still holds everything.

## Risks / Trade-offs

- [An owner who works in one room across many conversations must confirm it every time] → One `yes` on stored measurements, no retyping. This is the owner's decision 1.
- [Substring name matching may see two builds where the owner meant one, e.g. "shelf" in `shelf` and `wall-shelf`] → The Foreman asks instead of guessing, which is the safer failure. An exact package id match wins over name matches.
- [A build summary written before the switch may cover messages about another build] → The summary instruction keeps only the named piece; figures still come from the spec and house file.
- [The Foreman's routing call is spent on a turn that ends with a fixed question] → One cheap call; accepted for one routing path.
- [A design file sent before the room is confirmed is not imported then] → The owner attaches it again after one `yes`; the import never guesses a room.
- [Existing threads lose their implied room] → Stated in the proposal as a behaviour change. The next design turn asks once.

## Migration Plan

1. `uv run alembic upgrade head` applies `0014_conversation_rooms` (the service already runs migrations at start).
2. Existing threads keep their messages, binding and summary (moved to the build row). They have no confirmed room until the owner confirms one.
3. Existing generator-extension requests get no `thread_id`. Those with no piece stay in the house file and reach no prompt; those with a piece reach conversations that have that piece as a build.
4. Existing pieces keep `room_id`; those with none show "No room" on the Pieces page.
5. Rollback: the downgrade copies each active build's summary back to its thread, drops `thread_pieces`, the two thread columns and `generator_extension_requests.thread_id`. Pieces' rooms set meanwhile stay.

## Open Questions

None. Decided by the owner: a design-file import waits for the room; generator-extension requests record their conversation.
