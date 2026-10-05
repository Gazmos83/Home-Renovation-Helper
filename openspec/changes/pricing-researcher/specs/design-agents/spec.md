## MODIFIED Requirements

### Requirement: The Foreman routes each turn to one specialist
Each turn SHALL be handled by exactly one specialist — Intake, Designer, Builder or Researcher — chosen by the Foreman from the conversation and the house file, bounded by application rules: the Builder is never chosen when the thread has no bound piece with a built version, a thread with no piece and no confirmed brief goes to Intake unless the owner asks a question the Researcher answers (a price, a product, a guideline), and the Researcher prices only a bound piece's version. A pending confirmation SHALL resume in the specialist that raised it. The owner never names a specialist and a message cannot force one.

#### Scenario: New wish
- **WHEN** a thread has no piece and the owner describes what they want
- **THEN** Intake answers

#### Scenario: No piece, render asked
- **WHEN** a thread has no piece and the owner asks for a turntable
- **THEN** Intake or the Designer answers, explaining what must exist first; the Builder is not chosen

#### Scenario: Price question
- **WHEN** a thread's piece has a version and the owner asks what the boards will cost
- **THEN** the Researcher answers with a pricing of that version

### Requirement: Each specialist runs on its routed model with its instruction file
Each specialist SHALL call the model routed for its slot (`intake`, `designer`, `builder`, `researcher`; the Foreman on `foreman`) with that slot's generation profile, and SHALL be prompted from its checked-in instruction file: a header naming its tools (not editable) and text, followed by the fixed notes and the untrusted-content guard composed by code, exactly once and last. A missing or malformed instruction file SHALL stop startup naming the file.

#### Scenario: Prompt shape
- **WHEN** the Designer's prompt is assembled
- **THEN** it ends with the untrusted-content guard, contains it once, and binds exactly the tools its header names

#### Scenario: Instruction file missing
- **WHEN** `researcher.md` is absent
- **THEN** startup fails naming `researcher.md`

### Requirement: Room fit checks a placement against a house-file room
`room_fit` SHALL take a piece version, a room name, a wall index and an offset, read the piece's overall size and the room from the house file, and either refuse naming the wall and the excess in millimetres (or the ceiling, an opening or a furnishing in the way, or a design rule of severity `refuse`) or return the placement, any design-rule warnings with their sources, and the room-scene document a room render uses.

#### Scenario: Fits
- **WHEN** the bench is 1000 mm wide and placed at offset 500 on a 4000 mm wall with no opening there
- **THEN** the placement is returned

#### Scenario: Too wide
- **WHEN** the piece is wider than the remaining wall from its offset
- **THEN** it is refused naming the wall and the excess

#### Scenario: Fits with a guideline warning
- **WHEN** the piece fits but leaves less clear passage than a `warn` placement rule's limit
- **THEN** the placement is returned with the warning naming the rule and its source
