## Why

On 2026-10-17 the owner asked "How much space is between the murphy bed and wall 3?". The Designer answered correctly, 1350 mm, but wrapped the figure in an explanation:
- the wall the bed sits on and its offset;
- the bed's span;
- a `calc` block;
- a restating sentence.

The owner wants the plain answer, "The gap between the murphy bed and wall 3 is 1350 mm", with the working available but out of the way: a "Show the maths" button wherever the maths was used.

## What Changes

- **One figure, one sentence.** The formatting rules that code adds to every specialist's prompt gain a rule. A question that asks for one figure (a distance, gap, size, height, count or price) is answered in one sentence with the figure and its unit. How it was found (positions, lengths, steps) goes only in the `calc` block, never in the text.
- **"Show the maths".** In the conversation view, every `calc` block is hidden at first behind a "Show the maths" button in its place. Pressing it shows the framed calculation and turns the button into "Hide the maths". Nothing is sent and no turn starts. Replies without a `calc` block show no button.
- **Unchanged:**
  - `calc` blocks are still written whenever arithmetic is used, so the maths is always reviewable;
  - engineering reports and their own pages;
  - tables for lists with sizes.

Ladder: none. Agents: every specialist, through the code-composed formatting note only (no tool change). The **render guard** and the **bpy allow-list** are **not affected**.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `homeowner-chat`: the formatting rules add the one-sentence answer for a single figure, with the working only in `calc`.
- `studio-ui`: `calc` blocks sit behind "Show the maths" / "Hide the maths".

## Impact

- `backend/app/agent/prompts.py`: `FORMATTING_NOTE` gains the rule. `tests/test_prompts.py` (or the formatting-note test) checks it is composed once, unchanged by instruction edits.
- `frontend/src/components/chat/Reply.tsx`: the `language-calc` renderer becomes a small toggle component, with Vitest tests.
- No backend data, API or migration change.
