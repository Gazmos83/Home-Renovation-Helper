## 1. Formatting rule

- [x] 1.1 Append the one-figure rule to `FORMATTING_NOTE` in `backend/app/agent/prompts.py`. Verify with a prompts test that the composed Designer prompt holds the rule once, after the instruction text and before the guard, and that it is unchanged after an instruction edit ("Rules composed", "Not editable").

## 2. Show the maths

- [x] 2.1 Replace the `language-calc` branch in `frontend/src/components/chat/Reply.tsx` with a `CalcBlock` toggle ("Show the maths" / "Hide the maths", `aria-expanded`, local state). Verify with Vitest:
  - "Maths hidden at first";
  - "Calculation box" after pressing;
  - two blocks toggle independently;
  - "No maths, no button";
  - pressing sends no request.

## 3. Checks

- [x] 3.1 Run `uv run ruff check .` and the prompts tests in `backend/`. Run `pnpm lint`, `pnpm test` and `pnpm build` in `frontend/`. All must pass.
- [x] 3.2 Browser pass, with **no render tier**: in the Wohnen conversation, ask "How much space is between the murphy bed and wall 3?". The reply is one sentence with a "Show the maths" button, and pressing it shows the working. Also check that an older reply with a `calc` block now shows the button.
