## 1. Routing room corrections to Intake

- [x] 1.1 Update `app/agent/instructions/foreman.md`: extend the `intake` line and add the rule that a correction to a room's measurements, corners, angles, ceiling height, wall thickness or openings, or a new or revised plan, goes to `intake` even after the numbers are confirmed or a piece exists; narrow the `designer` line to changes to the piece. Verify `tests/test_instructions.py` gains a test asserting both lines and passes
- [x] 1.2 In `foreman()` (`app/agent/foreman.py`) add the code rule: when the latest owner message carries `upload_ids` and the bounded choice is `designer`, choose `intake`. Verify new tests in `tests/test_foreman.py`: a scripted `designer` decision on a turn with an attached upload and a confirmed brief is answered by Intake; the same decision without an upload stays with the Designer; a scripted `intake` decision for "bottom wall/left wall corner = 76°" on a thread with a confirmed brief and a bound piece reaches Intake (the bounding rules do not override it)
  - Applied to image uploads only: since `package-import`, a design file attached to a turn goes to the Designer (design-import spec), and that rule is checked last.

## 2. Honest refusal of a tool outside the specialist's set

- [x] 2.1 In `build_graph`, derive the tool → owning specialists map from the loaded instruction headers, and replace `NOT_AVAILABLE_NOTE` in `tools_node` with the three fixed refusal texts of design.md decision 3. Verify new tests in `tests/test_foreman.py`: the Designer calling `record_brief` gets a tool result naming `record_brief` and Intake and "Nothing was done", no interrupt is raised and the house file is unchanged; the Designer calling `cut_list` with the `cut_list` plugin switched off for the thread gets the "switched off in this conversation's tools" text; an unknown tool name gets the "There is no tool" text
- [x] 2.2 Add the shared plain-refusal sentence to `intake.md`, `designer.md`, `builder.md`, `lighting.md`, `reviewer.md` and `researcher.md`. Verify a `tests/test_instructions.py` test asserts every specialist file contains it

## 3. No promise after the turn

- [x] 3.1 Add to `builder.md` and `designer.md` that a started build's status shows in the conversation's Project panel and can be asked for in a later message, and that the specialist never promises to tell the owner later; add the no-later-promise sentence to `lighting.md` and `reviewer.md`. Verify a `tests/test_instructions.py` test asserts the sentence in those four files and that no instruction file contains "I'll tell you" or "let you know"

## 4. History shows every reply and answered confirmation

- [x] 4.1 In `tools_node`, attach `additional_kwargs={"confirmation": {subject, summary, answer, reason}}` to the `ToolMessage` of the first gated call when a `Confirmation` was answered (`yes` or `no`). Verify a `tests/test_foreman.py` test resumes a pending `revise` with `no` and reason "make it 4 shelves" and finds the kwargs on the stored tool message
- [x] 4.2 Change `chat.history` (`app/agent/chat.py`) to keep assistant messages with non-blank text whether or not they carry tool calls, and to emit a `confirmation` entry from the kwargs; widen `MessageOut.role` in `app/api/chat.py` to include `confirmation`. Verify new tests in `tests/test_chat_api.py`: a reply sent with a tool call is returned as an assistant entry; a whitespace-only text beside a tool call is not; an answered confirmation appears as one `confirmation` entry before the following reply; a pending confirmation is not a history entry; the no-internals test covers the history (no model slug, token figure, tool arguments or host path)

## 5. Studio

- [x] 5.1 Add `confirmation` to the message role type in `frontend/src/lib/api.ts` and render it in `routes/Conversation.tsx` as a muted bordered line ("Answered: <subject> — <answer>"; changed from "Confirmed:" by the owner on 2026-10-07, so a declined one reads correctly). Verify a `Conversation.test.tsx` test renders a history with a `confirmation` entry and finds its text

## 6. Verification

- [x] 6.1 Run `uv run ruff check .`, `uv run pytest -m "not slow"` (never two pytest processes at once), and `pnpm lint && pnpm test && pnpm build`. Verify all pass and record the counts in the commit message
  - 2026-10-07: ruff clean; `pytest -m "not slow"` 1494 passed, 29 skipped, 9 deselected (after the 6.2 fix); `pnpm lint` clean, `pnpm test` 65 passed, `pnpm build` ok.
- [x] 6.2 Browser check against the running backend, with no render (no tier involved): on a thread with a confirmed brief, send a corner-angle correction and see Intake propose the room; answer `no` and see the confirmation line stay in the history; ask the Designer for a revision and see its reasoning text shown above the confirmation card. Record the check in the commit message
  - Browser pass 2026-10-07: headless Chrome via playwright-core, with the API and Vite on a scratch database. Real routed models through OpenRouter.
    - A brief with a 4000 × 3500 mm living room was confirmed.
    - "the bottom wall/left wall corner is 76°" reached Intake (not the Designer). Intake asked which corner to keep, then proposed the corrected room.
    - Answering `no` with the reason "the ceiling is 2550 mm, not 2600" left the line "Confirmed: brief: … — no (the ceiling is 2550 mm, not 2600)" in the history after a reload.
    - The Designer created the bookshelf and revised its width; each answered confirmation stayed as a line before the reply that followed.
    - Found and fixed: while a confirmation was pending, text the specialist sent with the gated call sat in its sub-graph checkpoint and was not in the history. `chat.history` now adds the paused specialist's messages. Covered by a new `test_chat_api.py` test; the fake model gained a `(text, tool calls)` step.
    - Re-checked live: asked to explain first and revise the depth, the Designer's reasoning showed above the pending revise card.
    - No render was started.
