## Context

`pieces.brief` (JSONB) is copied from the Intake brief when a piece is created and never updated. The Reviewer reads it (`revision_review.run`: the stored brief wins over the conversation's) and prints it as "Brief: key: value; ...", from which "expected" figures come. `max_piece_height_mm` is the only measured field Intake writes besides the free-text purpose. A version's overall height comes from `derive.overall(document)`, as the Designer's piece summary computes it.

## Decisions

1. **Raise, never lower.** The limit is a ceiling the owner set; an approved version below it does not make the ceiling wrong. An approved version above it is the owner accepting a taller piece.
2. **In the approval route, in the approval's transaction**, beside the note clean-up: read the version's document, take the overall height, update the brief. A failure is logged and the approval stands.
3. **Record the source.** `max_piece_height_from_version` is added to the brief so the Reviewer text shows where the figure comes from; it is not a new column and no migration is needed.
4. **Free text and the conversation copy untouched.** Code cannot safely edit figures inside the purpose, and the conversation's brief copy is written only by Intake.

5. **Dismiss stale height items (owner's choice, 2026-10-13).** Existing items keep the text the Reviewer wrote, so they still read "expected max_piece_height_mm 2200" after the brief changes. On every new approval, open items of the approved version whose expected text names `max_piece_height_mm` with a number below the brief's current limit are set to `dismissed`. Matching is on the key name and the figure; no other item is touched and no text is rewritten. Running on every approval, not only when the limit rises, also clears items written before an earlier raise.

## Risks / Trade-offs

- A purpose that says "at most 2.2 m" still says so; the Reviewer sees both lines. Accepted; the owner can re-confirm the brief.
- A rounded height: the overall height is compared and stored as the integer millimetres the spec holds.
