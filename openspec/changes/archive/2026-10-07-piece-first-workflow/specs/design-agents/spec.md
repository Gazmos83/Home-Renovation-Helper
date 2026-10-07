## MODIFIED Requirements

### Requirement: Intake turns a wish into confirmed numbers
Intake SHALL collect the brief — the piece's purpose, its rough size and heights, style and budget, and the room (by name, or its measurements) when the owner gives one — ask for what is missing without inventing a figure, and propose the confirmed numbers through `record_brief`, which pauses for the owner's `yes`. A room SHALL NOT be required to confirm a brief: a brief without a room is complete and lets the Designer start. A room that is given SHALL be validated as before. On `yes` the room (when given), preferences and the brief are written to the house file; on `no` nothing is written and the reason returns to Intake.

#### Scenario: Numbers confirmed
- **WHEN** the owner confirms a hall 1200 mm wide and 2400 mm high with a 400 EUR budget
- **THEN** the house file holds the room and `budget_eur`, and the reply offers to design the piece

#### Scenario: Missing height
- **WHEN** the owner has not said how high the piece may be
- **THEN** Intake asks for the height and proposes no numbers

#### Scenario: Brief without a room
- **WHEN** the owner wants a listening wall about 2200 mm wide and 2200 mm tall in light oak for 900 EUR and names no room
- **THEN** `record_brief` previews the purpose, size, style and budget with "Room: not given yet", and on `yes` the brief is stored with no room and no room is written

#### Scenario: Designer follows a room-less brief
- **WHEN** a thread's brief was confirmed without a room and the owner asks to design the piece
- **THEN** the Designer answers, not Intake

### Requirement: The Designer creates a piece from a validated spec
The Designer SHALL emit a complete custom-build document, starting from a shipped template and changing only what the brief supports, and call `create_piece` with it and a package id. The shipped templates SHALL include a generic starter, `custom-build`, with one visible cabinet module (carcass, back, shelves and doors), offered to the Designer first; the Designer SHALL start from it unless another shipped template fits the brief better. Every shipped template SHALL validate against the schema and derive at least one cut-list row, except `blank-build`. The document SHALL be validated against the schema before anything else; a valid one is previewed (name, overall size in mm, module count, cut-list rows, hardware lines) and pauses for `yes`. On `yes` the piece and version 1 are recorded and the build starts; on `no` nothing is created and the reason returns to the Designer. A package id already in use SHALL be refused.

#### Scenario: Create confirmed
- **WHEN** the owner answers `yes` to a previewed hall bench
- **THEN** `hall-bench/v1` exists with the input document, the piece is recorded, and the build is queued

#### Scenario: Invalid document skips the pause
- **WHEN** the Designer's document fails validation
- **THEN** no confirmation is raised and the refusal naming the field returns to the Designer

#### Scenario: Starter template builds something visible
- **WHEN** the `custom-build` template is validated and derived
- **THEN** it is valid, has one module with a carcass, a back, shelves and doors, and derives cut-list rows and hardware lines

#### Scenario: Starter offered first
- **WHEN** the Designer's prompt is assembled
- **THEN** the template note names `custom-build` before the other templates

### Requirement: Room fit checks a placement against a house-file room
`room_fit` SHALL take a piece version, a room name, a wall index and an offset, read the piece's overall size and the room from the house file, and either refuse naming the wall and the excess in millimetres (or the ceiling, an opening or a furnishing in the way, or a design rule of severity `refuse`) or return the placement, any design-rule warnings with their sources, and the room-scene document a room render uses. A room that is not in the house file SHALL be refused naming the room, listing the rooms that are, and saying that Intake records a room from its measurements or a plan; a room is required here even when the piece's brief has none.

#### Scenario: Fits
- **WHEN** the bench is 1000 mm wide and placed at offset 500 on a 4000 mm wall with no opening there
- **THEN** the placement is returned

#### Scenario: Too wide
- **WHEN** the piece is wider than the remaining wall from its offset
- **THEN** it is refused naming the wall and the excess

#### Scenario: Fits with a guideline warning
- **WHEN** the piece fits but leaves less clear passage than a `warn` placement rule's limit
- **THEN** the placement is returned with the warning naming the rule and its source

#### Scenario: No room yet
- **WHEN** the piece was designed from a room-less brief and the house file has no room `Wohnen`
- **THEN** `room_fit` for `Wohnen` is refused naming `Wohnen`, saying no rooms are recorded yet and that Intake records a room
