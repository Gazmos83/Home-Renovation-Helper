## ADDED Requirements

### Requirement: Inspector dimensions have one reader
A composition version's wall lengths and ceiling heights SHALL be produced by one function reading the version's stored document, used by the inspector's dimensions route and by the chat. A document with no room plan SHALL yield no dimensions rather than a guess.

#### Scenario: Same figures in both places
- **WHEN** the dimensions route and the chat read Wohnen version 2
- **THEN** both return the same five wall lengths and the same ceiling height

### Requirement: Placement uses the approved room plan
When a room has a composition version with a stored room plan, `room_fit` and `compose_room` SHALL check walls, openings and ceiling against the approved version of that composition (or the latest when none is approved), the same document the inspector dimensions come from. When there is no composition or the document has no room plan, they SHALL use the house-file room as today.

#### Scenario: House-file door does not block when the approved plan has none there
- **WHEN** Wohnen version 2 is approved, its plan has no door on wall 2 at 850–1850 mm, the house-file room still lists that door, and the owner asks to place a piece along wall 2 clear of other openings on the approved plan
- **THEN** the placement check does not refuse for that house-file door

#### Scenario: No composition keeps house-file openings
- **WHEN** the room has no composition and the house-file room has a door on wall 0 under the piece
- **THEN** `room_fit` refuses naming that door as today
