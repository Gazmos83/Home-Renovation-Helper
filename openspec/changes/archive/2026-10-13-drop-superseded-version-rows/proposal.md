## Why

The "Decisions so far" note collects rows such as "Listening wall: version 3 saved". Once a newer version is approved, a row that only records an older version being saved no longer helps the chat move the build forward, and it crowds the table. The owner wants those rows gone on their own, while the versions themselves stay available.

## What Changes

- When a version of a piece is approved, the app removes from the note of every conversation bound to that piece the rows that only record an older version (lower than the approved one) being saved.
- A row that states a decision (for example "version 2 had the doors on top; moved to the bottom") is never removed, and neither is any row that does not name an older version of that piece.
- Versions, their folders, reviews, renders and records are not touched. Nothing is deleted by approval.
- A note left with no rows is not saved empty; it is kept as it was.
- Nothing is asked of the owner and no model is called.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `homeowner-chat`: the conversation note drops its "older version saved" rows when a newer version of the piece is approved.

## Impact

- Backend: the approval route (`api/packages.py`) and a small function beside `app/agent/decisions_note.py`; both use the existing note save and row rules.
- No frontend change; the panel reads the note again on its next load.
- No migration, no new setting, no model or tool change.
