## ADDED Requirements

### Requirement: A revision past the version limit is refused by code
When a piece already holds 15 versions, `revise_package`, and the rebuild of an unchanged piece, SHALL refuse before asking for confirmation. The refusal SHALL be written by code and SHALL say that the piece has 15 versions and that the owner can delete one on the Pieces page or in the Project panel and then ask again. The Designer SHALL relay that refusal and SHALL NOT propose deleting a version itself. When the new version would be the 13th, 14th or 15th the piece holds, the confirmation summary SHALL add a line written by code: "This will be version <n> of 15 the piece can hold."

#### Scenario: Revision refused at the limit
- **WHEN** `listening-wall` holds 15 versions and the owner asks "make the shelves 20 mm thicker"
- **THEN** no confirmation is shown, no version is made, and the reply says the piece has 15 versions and one can be deleted on the Pieces page or in the Project panel

#### Scenario: Heads-up near the limit
- **WHEN** `listening-wall` holds 12 versions and the Designer proposes a revision
- **THEN** the confirmation summary includes "This will be version 13 of 15 the piece can hold."

#### Scenario: No heads-up early
- **WHEN** `listening-wall` holds 4 versions and the Designer proposes a revision
- **THEN** the confirmation summary has no version-limit line
