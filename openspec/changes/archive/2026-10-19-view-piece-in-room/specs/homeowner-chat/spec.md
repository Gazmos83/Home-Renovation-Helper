## ADDED Requirements

### Requirement: Missing information is asked for, not explained
When a request cannot go on because something the owner can give is missing (a size, a height, a room, a placement, a choice), the reply SHALL ask for it as questions: through a question set when the specialist has one, one question per missing item, in the owner's terms. The reply SHALL NOT list what a tool or document lacks, and SHALL NOT name a tool, an internal document, a schema field or a JSON key. A refusal from a tool that the owner cannot resolve SHALL be stated in one plain sentence saying what happens next.

#### Scenario: Room view without a placement
- **WHEN** the owner asks to see a built piece in the room and no placement exists
- **THEN** the owner is asked where to place it, and the reply names no `room_fit`, "room document", `kind`, `schema_version` or other field

#### Scenario: Brief with missing figures
- **WHEN** Intake lacks the height and the budget
- **THEN** the owner gets a question set with the two questions, not a paragraph describing what the brief lacks
