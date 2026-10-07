## MODIFIED Requirements

### Requirement: The Foreman routes each turn to one specialist
Each turn SHALL be handled by exactly one specialist (Intake, Designer, Builder, Researcher, Reviewer or Lighting & materials), chosen by the Foreman from the conversation and the house file. Application rules bound the choice:
- The Builder is never chosen when the thread has no bound piece with a built version.
- The Reviewer is never chosen unless the bound piece's latest version has a screenshot or a render.
- Lighting & materials is never chosen unless the bound piece's latest version has a successful build.
- A thread with no piece and no confirmed brief goes to Intake, unless the owner asks a question the Researcher answers (a price, a product, a guideline).
- The Researcher prices only a bound piece's version.

A pending confirmation SHALL resume in the specialist that raised it. The owner never names a specialist and a message cannot force one.

#### Scenario: New wish
- **WHEN** a thread has no piece and the owner describes what they want
- **THEN** Intake answers

#### Scenario: No piece, render asked
- **WHEN** a thread has no piece and the owner asks for a turntable
- **THEN** Intake or the Designer answers, explaining what must exist first; the Builder is not chosen

#### Scenario: Price question
- **WHEN** a thread's piece has a version and the owner asks what the boards will cost
- **THEN** the Researcher answers with a pricing of that version

#### Scenario: Review asked with nothing rendered
- **WHEN** the bound piece's latest version has no screenshot or render and the owner asks for a check
- **THEN** the Reviewer is not chosen and the reply says what must exist first

#### Scenario: Photoreal detail asked on a built piece
- **WHEN** the bound piece's latest version is built and the owner asks for realistic oak and soft lighting
- **THEN** Lighting & materials answers

#### Scenario: Photoreal detail asked with nothing built
- **WHEN** the bound piece has no built version and the owner asks for photoreal detail
- **THEN** Lighting & materials is not chosen and the reply says the piece must be built first

### Requirement: Each specialist runs on its routed model with its instruction file
Each specialist SHALL call the model routed for its slot (`intake`, `designer`, `builder`, `researcher`, `reviewer`, `lighting`; the Foreman on `foreman`) with that slot's generation profile. It SHALL be prompted from its checked-in instruction file: a header naming its tools (not editable) and text, followed by the fixed notes and the untrusted-content guard composed by code, exactly once and last. The tools a header may name SHALL be the tools the plugin manifests declare. A specialist SHALL bind only the named tools whose plugin is enabled for the thread, plus enabled HTTPS plugins for its role. A missing or malformed instruction file SHALL stop startup naming the file.

#### Scenario: Prompt shape
- **WHEN** the Designer's prompt is assembled
- **THEN** it ends with the untrusted-content guard, contains it once, and binds exactly the tools its header names that are enabled for the thread

#### Scenario: Instruction file missing
- **WHEN** `reviewer.md` is absent
- **THEN** startup fails naming `reviewer.md`

#### Scenario: Header names an undeclared tool
- **WHEN** `designer.md` names a tool no manifest declares
- **THEN** startup fails naming `designer.md` and the tool

#### Scenario: Lighting on its slot
- **WHEN** the Lighting & materials specialist answers a turn
- **THEN** the call uses the model routed for `lighting` and binds only the detail-pass tools enabled for the thread

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
