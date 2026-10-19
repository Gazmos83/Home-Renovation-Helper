## Context

See proposal.md for the evidence from thread `7fea661f` (2026-10-18). The relevant current state in code:

- `measurements.owner_texts_since_version` collects only `HumanMessage` texts after the last "Created <id> version" tool result. `ask_owner` answers live only in a `ToolMessage`'s text: `"The owner answered:\n1. <question> → <answer> <unit>"`, or `"…wrote instead: \"<text>\"…"`.
- `engineering_chat.engineering_intent` is `_ENGINEERING` (load/safety terms and hardware words in one pattern) or `kitchen_intents` (which matches "hanger"). The Foreman makes a turn engineering when code or the routing model's `engineering_question` flag says so (`foreman.py:1064`). On an engineering turn, `render_answer` returns only `SHORT_STATUS` for anything that is not valid answer JSON.
- `room_answer` reads a decline only after `ROOM_OFFER`. `room_question_asked` only suppresses the offer for the one turn right after `ROOM_QUESTION`.
- Composition items resolve to `base_mm` only for the ceiling layer, and `_composition.py` already lifts an item by `base_mm`. `room_contract` takes `{wall, offset_mm}` for the package, and `build_room_scene` puts the package on the floor (`-floor_z`).
- The saved placement (`placements/<room>.json`, written by `room_fit` and `ask_placement`) is read only as a yes/no `placement_ready`, never shown to a specialist.

## Goals / Non-Goals

**Goals:** each fix is enforced in code, not by prompt text alone; old documents and placement files stay valid unchanged.

**Non-Goals:**
- Changing the summary note, the recent-inputs window or the memory settings.
- Changing Foreman routing beyond the engineering flag and the room decline.
- A height for stand-ins, models or LED strips (strips already have `mount_height_mm`).
- Free (x, y) placements that hang.

## Decisions

1. **Owner words from forms are read from the code-written record, not parsed from text.**
   - The tools node already stores every answered form on its `ToolMessage` as `additional_kwargs["answers"]`: rows of `{question, answer}` with the unit appended, or `declined` with the owner's free text. It does this for `ask_owner` and `ask_placement`.
   - `owner_texts_since_version` returns the human texts plus each row's answer (or the declined text), in order; question text is never included.

   *Alternative:* parse "→" in the result text. Rejected: question text can contain "→" and figures, while the record cannot be forged by the model, since only the tools node writes it.
2. **Refusals quote the sentence.** For a quote not found or an uncovered length, the refusal adds the owner's sentence (split on `.`, `!`, `?`, line breaks) that contains the length, neutralised and capped at 200 characters.
3. **Engineering terms are split in two.** `_ENGINEERING` becomes two patterns:
   - `_HARDWARE`: hinge, drawer, runner, wall/base/kitchen cabinet, worktop, countertop and their German words;
   - `_LOAD`: everything else, plus `allowable\s+(?:\w+\s+)?span`, `shelf span`, `sag\w*` and `durchh[äa]ng\w*`.

   `engineering_intent(text)` stays the union, so every current caller keeps its behaviour. A new `revision_engineering(text)` (used only when the Foreman sees `revision_intent` and a bound package) is true only for `_LOAD` or the kg pattern, so a revision that only names hardware or matches `kitchen_intents` is not an engineering turn.
4. **One ordinary retry for a model-only flag.**
   - The Foreman records `engineering_by_code = engineering_intent(last owner text)` in state.
   - In the specialist `agent` node, when the turn is engineering, `engineering_by_code` is false, the reply is final (no tool calls) and `render_answer` would return exactly `SHORT_STATUS`, the node calls the model once more with the engineering note, the engineering-only tools and the engineering flags removed, and uses that reply.
   - Tool rounds already taken still count against `MAX_TOOL_ROUNDS`. The retry happens at most once per turn (a state flag).

   *Alternative:* drop the model's flag entirely. Rejected: genuine engineering questions in wording code misses would lose the evidence path.
5. **Room decline after the question.** `room_answer` also handles `ROOM_QUESTION` as the last reply: it returns "room" when a room is named or a plan or photo is attached; "no" when the first word is in a new `ROOM_NO_WORDS` set; otherwise `None` (Intake handles it as today). `load_house`'s existing `answer == "no"` branch then calls `decline_room`.
6. **`mount_height_mm` is one optional field in three contracts.**
   - `composition_contract._WALL_PLACEMENT` gains it as optional, allowed only on `piece` items. The resolver sets `base = mount_height_mm` and records `base_mm` for a hung piece, and the clash test uses height ranges when either item is hung (as it already does for the ceiling layer). `_blocked_opening` already takes `base`.
   - `room_contract._PLACEMENT_KEYS` gains it as optional, with the ceiling check against the package's overall height, and `build_room_scene` adds it to the empty's z.
   - The placement JSON stores it when given.

   The name matches the LED strip's existing `mount_height_mm` (height above the floor). *Alternative:* a `layer: "wall"`. Rejected: it still needs a height, and layers are for stand-ins and models.
7. **Where the height comes from.**
   - `ask_placement` gains an optional `hung: true` argument. With it, a third code-written question asks for the underside height above the floor (or the gap below the ceiling, converted by code from the ceiling height and the piece's height).
   - `room_fit` gains an optional `mount_height_mm` argument, which the Designer may fill only from the owner's words. It is checked like `revise_package`'s `requested` entries with target `none`, so the figure must be in the owner's words.
   - `compose_room` copies the stored placement's height when the Designer places that piece.
8. **The placement line in the notes.** `load_house` already reads the placement for `placement_ready`. It now also formats one line, for example: `Saved place in Wohnen: wall 2, 0 mm from its left end, hung with its underside at 1700 mm.` That line is appended to the Designer's and the Builder's notes.

## Risks / Trade-offs

- [A retried ordinary answer could state an unverified load claim] → the retry happens only when code finds no engineering term in the owner's message; the existing safety notes in every specialist's instructions still apply. A test asserts that a message with a load term never retries.
- [Splitting the pattern changes which revision turns are engineering] → `engineering_intent` is unchanged for every other caller; tests cover "add a wall hanger" (not engineering) and "add a hanger that holds 30 kg" (engineering).
- [A placement saved before this change has no height] → absent means on the floor, which is what it was.
- [The composition generator change touches a Blender path] → the existing `base_mm` path is reused. One `--blender` composition build of a hung piece checks its world z.

## Migration Plan

No database migration. The new fields are optional in JSON documents, and old documents parse unchanged. Rollback is a code revert; a document saved with `mount_height_mm` would then be refused by name, so revert only before hung pieces are saved.
