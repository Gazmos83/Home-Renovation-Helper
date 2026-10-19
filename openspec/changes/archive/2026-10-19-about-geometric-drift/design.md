## Context

`About.tsx` has an intro and three `h2` sections. The About requirement forbids technical terms (model, prompt, token, frame, resolution, engine). The word "model" in the draft means a 3D model, but the page test may refuse the word "model".

## Decisions

- **Placement.** The new section goes last, after "Take your furniture anywhere", so the existing order is kept.
- **Wording.** It is said plainly ("drift", "redraws") with one concrete example from the owner's own tests (an open cubby that gains a door). The words "geometric drift" are not used, because they are a technical term. The owner approved the wording without it (2026-10-19).
- **"Model" word.** `About.test.tsx` refuses "model name", not "model", so "3D model" may stay, as it already does in "Take your furniture anywhere".
