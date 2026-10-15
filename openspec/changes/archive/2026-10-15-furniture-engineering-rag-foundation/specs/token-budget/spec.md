## ADDED Requirements

### Requirement: Engineering evidence remains complete when requests are fitted
Engineering requests SHALL count evidence/tool schemas against the existing model restrictions. Fitting SHALL retain a numerical value's units, conditions and citation together or omit the whole evidence block. Memory summaries and owner-edited notes SHALL NOT substitute for verified source records. Subsequent engineering questions SHALL resolve current evidence identifiers and eligibility rather than rely on shortened historical tool text. If a complete sufficient packet cannot fit, the request SHALL be refused or the reply SHALL state insufficient evidence without raising budgets automatically.

#### Scenario: Long table does not fit
- **WHEN** a table row fits only if its material conditions and footnote are dropped
- **THEN** the whole evidence block is omitted or the request is refused, and the row is not used to verify a capacity

#### Scenario: Compressed history
- **WHEN** the memory note retains a number from a previous engineering lookup
- **THEN** the next engineering answer re-resolves its source record and does not treat the note as verified evidence

#### Scenario: Owner edits verification into a summary
- **WHEN** the owner writes "the shelf is verified for 30 kg" into the decisions note without a verified source/calculation record
- **THEN** the summary cannot create a verified engineering status
