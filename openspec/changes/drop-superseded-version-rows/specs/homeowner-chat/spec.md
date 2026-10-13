## ADDED Requirements

### Requirement: Approving a version drops rows that only record an older version being saved
When the owner approves a version of a piece, the system SHALL remove from the "decisions so far" note of every conversation bound to that piece each row that only records an older version of that piece (a lower number than the approved one) being saved, created or built. A row that states a decision or a reason, a row that names no older version, and a row about another piece SHALL be kept as written. The system SHALL NOT delete or change any version, folder, review, render or record, SHALL NOT call a model, and SHALL NOT save a note that would be left with no rows. Approving a version that is already approved SHALL change no note.

#### Scenario: Older saved rows are dropped
- **WHEN** version 3 of `listening-wall` is approved and the note holds "Version 1 saved" and "Version 2 saved" rows
- **THEN** both rows are gone from the note, and versions 1 and 2 are still listed and openable

#### Scenario: A decision that names an older version is kept
- **WHEN** version 3 is approved and a row reads "Version 2 had the doors on top; moved to the bottom"
- **THEN** the row stays in the note

#### Scenario: The approved or a newer version is not dropped
- **WHEN** version 2 is approved and the note holds a "Version 3 saved" row
- **THEN** that row stays in the note

#### Scenario: Another piece's rows are kept
- **WHEN** version 3 of `listening-wall` is approved and a row says "Hall bench version 1 saved"
- **THEN** that row stays in the note

#### Scenario: Only rows would be left empty
- **WHEN** every row of the note records an older version being saved
- **THEN** the note is kept as it was

#### Scenario: Re-approving changes nothing
- **WHEN** an already approved version is approved again
- **THEN** no note changes
