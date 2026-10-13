## ADDED Requirements

### Requirement: Approving a taller version raises the brief's height limit
When the owner approves a version of a piece whose overall height is greater than the piece's stored brief limit for the highest the piece may be, the system SHALL raise that limit in the stored brief to the version's overall height and record the version it came from. When the version is not taller than the limit, or the brief states no limit, the brief SHALL NOT change. No other field of the brief SHALL change, and unapproving a version SHALL NOT lower the limit. A review SHALL read the brief with this limit, so it does not expect a height below one the owner has approved.

#### Scenario: A taller approved version raises the limit
- **WHEN** the stored brief says the piece may be at most 2200 mm high and the owner approves a version that is 2238 mm high
- **THEN** the brief's limit is 2238 mm, it names that version, and the next review of the piece expects at most 2238 mm

#### Scenario: A lower version leaves the limit
- **WHEN** the limit is 2200 mm and the approved version is 2100 mm high
- **THEN** the brief's limit stays 2200 mm

#### Scenario: Nothing else in the brief changes
- **WHEN** the limit is raised
- **THEN** the brief's room, purpose, style and budget are as they were

#### Scenario: No limit stated
- **WHEN** the stored brief states no height limit and a version is approved
- **THEN** the brief is unchanged

#### Scenario: Unapproving keeps the limit
- **WHEN** the approved version that raised the limit is unapproved
- **THEN** the limit stays at the raised height

### Requirement: Approving a version dismisses its items that expect an older height limit
When the owner approves a version, the system SHALL mark as dismissed each open review item of that version whose expected text states the highest the piece may be (`max_piece_height_mm`) as a figure lower than the brief's current limit. This SHALL happen on every approval, including one that raises no limit. It SHALL NOT change any other item, SHALL NOT rewrite any review or item text, and SHALL NOT touch items of other versions. Dismissed items stay stored and the owner can still read them.

#### Scenario: Items expecting the old limit are dismissed
- **WHEN** version 17 has open items expecting "max_piece_height_mm 2200.0" and the brief's limit is 2238, and the owner approves version 17
- **THEN** those items are dismissed and no longer appear among the open items

#### Scenario: Other items stay open
- **WHEN** the same version has an open item expecting doors over the bottom two shelves
- **THEN** that item stays open

#### Scenario: Approving again clears earlier items
- **WHEN** the limit was already raised to 2238 by an earlier approval and the owner approves the version again
- **THEN** its open items that expect 2200 are dismissed

#### Scenario: Other versions are untouched
- **WHEN** version 16 has open items expecting 2200 and version 17 is approved
- **THEN** version 16's items stay open
