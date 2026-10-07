## MODIFIED Requirements

### Requirement: The Foreman routes each turn to one specialist
Each turn SHALL be handled by exactly one specialist (Intake, Designer, Builder, Researcher, Reviewer or Lighting & materials), chosen by the Foreman from the conversation and the house file. Application rules bound the choice:
- The Builder is never chosen when the thread has no bound piece with a built version.
- The Reviewer is never chosen unless the bound piece's latest version has a screenshot or a render.
- Lighting & materials is never chosen unless the bound piece's latest version has a successful build.
- A thread with no piece and no confirmed brief goes to Intake, unless the owner asks a question the Researcher answers (a price, a product, a guideline), or asks to compose a room while the house file holds an approved piece version or a composition (the Designer).
- A thread with no piece and no confirmed brief SHALL also go to the Designer when the Foreman chose the Designer and the owner's message, or the reply just before it, names a piece in the house file by its package id or its name. This is so that the piece can be revised, rebuilt or given an imported version.
- The Researcher prices only a bound piece's version.
- A turn that carries a design file goes to the Designer, whatever the thread holds.

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

#### Scenario: Design attached in a new thread
- **WHEN** a thread has no piece and no brief and the owner sends "import this" with a design file attached
- **THEN** the Designer answers, not Intake

#### Scenario: Compose request in a new thread
- **WHEN** a thread has no piece and no brief, the house file holds an approved version of `bench`, and the owner asks to compose `Wohnen` with it
- **THEN** the Designer answers, not Intake

#### Scenario: Revise a named piece from a new thread
- **WHEN** a thread has no piece and no brief, the Designer's last reply named `murphy-bed`, and the owner answers "Revise it"
- **THEN** the Designer answers, not Intake

#### Scenario: No piece named
- **WHEN** a thread has no piece and no brief and the owner writes "revise it" without any reply or message naming a piece in the house file
- **THEN** Intake answers

## ADDED Requirements

### Requirement: The Designer rebuilds a piece unchanged as a new version
`rebuild_piece` SHALL take a piece's package id. It previews "version N+1, rebuilt unchanged from version N", where N is the latest version, and pauses for `yes`. On `yes`:
- the next version is recorded with a copy of version N's stored design and the change line `rebuilt unchanged from version N`;
- the conversation is bound to the piece;
- the headless build starts.

Version N's folder and record SHALL be untouched, and the new version is not approved until the owner approves it. An unknown package id, or a latest version without a readable design, SHALL be refused with nothing created. On `no` nothing is created and the reason returns to the Designer.

#### Scenario: Rebuilt for new views
- **WHEN** the owner asks for the Murphy bed as a new version without changes, and answers `yes`
- **THEN** `murphy-bed` version 2 exists with the same design as version 1 and the change line `rebuilt unchanged from version 1`, its build is queued, and version 1 is unchanged

#### Scenario: Declined
- **WHEN** the owner answers `no` to the rebuild preview
- **THEN** no version or folder is created

### Requirement: A specialist's empty answer is never the turn's reply
When a specialist's final answer has no text and no tool call, the specialist SHALL be called once more with a note that its answer was empty. If the second answer is also empty, the turn SHALL end with a fixed reply naming the specialist by role and asking the owner to rephrase or ask again. Both calls SHALL be counted against the slot's token budget like any other.

#### Scenario: Empty then answered
- **WHEN** Intake's first answer to "Revise it" is empty and its second is a sentence
- **THEN** the owner sees the sentence and no empty entry

#### Scenario: Empty twice
- **WHEN** Intake answers empty twice
- **THEN** the turn's reply says Intake gave no answer and asks the owner to rephrase or ask again
