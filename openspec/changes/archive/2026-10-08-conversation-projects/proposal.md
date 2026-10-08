## Why

Every turn loads the whole house file into the prompt: all rooms, all pieces, all apartments, all compositions and every open generator-extension request. A conversation about one hall bench still carries the living room, the listening wall and the Murphy bed. That costs tokens, and it lets the Foreman and the specialists mix up pieces and rooms. The room is also assumed: a room measured last month is used without the owner saying it is the one, and a piece is tied to a room only when the brief happened to name it.

## What Changes

- **A conversation confirms its room.** Each conversation names its room (or apartment) and the owner confirms it in that conversation. Stored measurements may be offered for that confirmation, but nothing from them is used before the owner says yes. Intake gets one gated tool, `confirm_room`, for this. A confirmed brief with a room, and a confirmed plan, also confirm the conversation's room.
- **The Foreman asks first.** While a conversation has no confirmed room, a turn that would start design work gets one fixed reply from the Foreman: "Which room is this for?". This includes a turn that carries a design file: the import waits until the room is confirmed and then records the piece in that room. The Researcher still answers price and product questions.
- **Several builds per conversation.** A conversation keeps a list of the builds (pieces) worked on in it. One is the active build. Naming a build switches to it. The owner can switch the conversation's room, and can move any build to another room.
- **A piece belongs to a room.** `create_piece` records the piece in the conversation's room. Existing pieces without a room stay unassigned until the owner attaches them, either in a conversation or with a room selector on the Pieces page.
- **Scoped loading.** The prompt carries the active room (or apartment) and the active build in full. Every other build of this conversation gets one line. Rooms and builds outside the conversation are left out. Generator-extension requests now record the conversation they were made in; the prompt carries the open requests of the conversation's builds and those made in the conversation. Older requests with neither a piece nor a conversation stay in the house file and reach no prompt. The house file keeps everything; only what the prompt carries changes. Scoping is done in code, and the instruction files do not grow.
- **One summary per build.** The "decisions so far" summary is kept per build in the conversation, not per conversation. Switching builds brings back that build's summary. Figures still come only from the spec JSON and the house file.
- **Ambiguity is asked.** When the owner's message names two builds of the conversation, the Foreman asks which one instead of guessing.
- **BREAKING (behaviour).** The house-file scenario "A second piece starts with the room known" no longer holds: a new conversation does not see rooms or pieces from other conversations until the owner confirms the room. A brief without a room no longer lets the Designer start. CLAUDE.md §9a is reworded to match.
- Ladder and agents: ladder **step 1** only (spec change flow). It touches the Foreman (routing rules and the two fixed questions), Intake (`confirm_room`), the Designer (piece room, scoped note) and the context every specialist reads. The Builder, Reviewer, Lighting & materials and Researcher keep their tools. **The render guard and the bpy allow-list are not affected.** No render is started by this change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `house-file`: a piece belongs to a room and can be moved; a generator-extension request records its conversation; a thread records its confirmed room or apartment, its builds and one summary per build; the turn's context is scoped to the conversation; compositions reach the turn only for the active room or apartment.
- `design-agents`: the Foreman asks for the room before design work, a design-file import included, and asks which build when a reference is ambiguous; Intake confirms the conversation's room; a brief without a room no longer starts the Designer; a new piece is recorded in the conversation's room.
- `homeowner-chat`: a turn adds the piece it creates or revises to the conversation's builds and makes it the active build; naming one build switches to it.
- `token-budget`: the summary that stands in for dropped exchanges is the active build's summary.
- `studio-ui`: the Pieces page shows each piece's room and lets the owner attach or change it.

## Impact

- Backend: `app/db/models.py` and a new migration `0014_conversation_rooms` (thread room and apartment, `thread_pieces` with per-build summary, `generator_extension_requests.thread_id`); `app/agent/tools/base.py` (`record_unknown_fields` passes the conversation); `app/agent/house_file.py` (thread room, builds, per-build summary, piece room); `app/agent/foreman.py` (`load_house` scoping, room gate, ambiguity check, `piece_named`); `app/agent/prompts.py` (`house_note`, `composition_note` take the scoped data); `app/agent/summaries.py` (keyed by build); `plugins/intake/` (`confirm_room`), `plugins/create_piece/tool.py` (room from the conversation), `plugins/design_import/tool.py` (imported piece in the conversation's room); `app/api/packages.py` (room on the list, attach route), a new `app/api/rooms.py` (room names).
- Frontend: `src/lib/api.ts`, `src/routes/Pieces.tsx` (room selector).
- Docs: CLAUDE.md §9a wording.
- Tests: `test_house_file.py`, `test_foreman.py`, `test_design_import.py`, `test_summaries.py`, `test_prompts.py`, `test_chat_turns.py`, `test_packages_api.py`, a migration test, `Pieces.test.tsx`.
- No new dependency, no change to `config/`.
