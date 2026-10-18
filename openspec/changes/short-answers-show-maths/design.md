## Context

See proposal.md (Why). Today:
- `prompts.FORMATTING_NOTE` is composed by code after each specialist's instruction text and before the untrusted-content guard. It already asks for arithmetic in fenced `calc` blocks.
- `Reply.tsx` renders Markdown and, for a code element with class `language-calc`, a framed box.

## Goals / Non-Goals

**Goals:**
- Short answers to single-figure questions, from every specialist, without editing each instruction file.
- The working stays in the reply, hidden until asked for.

**Non-Goals:**
- Post-processing model replies in code to cut text. That is too brittle, and a rule in the composed note is the established lever.
- Changing how engineering calculator reports are produced or shown.
- Remembering opened maths across reloads.

## Decisions

1. **A rule in the composed note, not per-agent instructions.** One bullet is appended to `FORMATTING_NOTE`:

   > "When the owner asks for one figure (a distance, gap, size, height, count or price), answer in one sentence that gives the figure and its unit, for example "The gap between the murphy bed and wall 3 is 1350 mm." Put how you found it (positions, lengths, steps) only in a `calc` block after that sentence; do not explain it in the text."

   Because the note is composed by code, an edit of an instruction file cannot drop the rule. This matches the existing rule's guarantee.

2. **A `CalcBlock` toggle in `Reply.tsx`.** The `language-calc` branch renders `<CalcBlock text=…/>`: a small outline button "Show the maths" with `aria-expanded`, and the existing framed box when open. State is local (`useState(false)`), so each block toggles on its own, nothing is sent, and a reload starts closed. The box keeps its current styling. The button sits where the block was, so the reading order is unchanged.

## Risks / Trade-offs

- **[A model still adds a sentence or two]** → the rule's example is concrete. The owner can report a case, and the rule text is then tightened. No code filter is added.
- **[The owner misses working that matters]** → every `calc` block keeps a visible button. Tables and warnings are not hidden.

## Migration Plan

None. Old replies with `calc` blocks show the button too.
