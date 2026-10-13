## Why

The brief states "the highest the piece may be: 2200 mm", and the owner has since approved a version that is 2238 mm high. The Reviewer still reads the stored brief, so its expected figure stays 2200 and a review of the approved version flags the owner's own approved height as too tall. Approving a version is the owner accepting its measurements; the expectation should follow.

## What Changes

- When a version is approved, the piece's stored brief raises `max_piece_height_mm` to that version's overall height if the version is taller than the stored limit. A lower or equal height leaves the limit as it is, since the limit is a ceiling.
- Nothing else in the brief changes: room, purpose (free text), style and budget stay as the owner confirmed them.
- The change is recorded in the brief itself, as `max_piece_height_from_version`, so the Reviewer can say where the limit now comes from.
- When a version is approved, its open review items that expect a height limit lower than the brief's current limit are marked dismissed, since the approval accepted that height. This also runs when the limit was already raised, so approving again clears items written before the raise. Items about anything else stay open, and no review text is rewritten.
- Unapproving does not lower the limit again; the owner can change it by confirming a brief.
- No model is called, nothing is deleted, and versions are untouched.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `render-review`: the brief a review compares against carries the approved version's height as the highest the piece may be, when that version is taller than the stated limit.

## Impact

- Backend: the approval route in `api/packages.py` (a small function beside the approval), the brief JSON on `pieces`, tests.
- Not covered: figures written inside the purpose text (for example "2.2 m wall unit") and the conversation's own copy of the brief, which only the Intake tool writes. The Designer's piece summary already carries the approved version's real height.
