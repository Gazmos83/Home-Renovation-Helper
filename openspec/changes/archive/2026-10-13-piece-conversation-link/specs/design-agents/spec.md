## MODIFIED Requirements

### Requirement: The Foreman routes each turn to one specialist
Each turn SHALL be handled by exactly one specialist (Intake, Designer, Builder, Researcher, Reviewer or Lighting & materials), chosen by the Foreman from the conversation and the house file, or answered by the Foreman with one of its fixed questions below. Application rules bound the choice, in this order:
- A question the Researcher answers (a price, a product, a guideline) goes to the Researcher, with or without a confirmed room.
- While the conversation has no confirmed room or apartment, a turn that carries a plan or photo, names a room or apartment of the house file, or answers the Foreman's room question goes to Intake. Any other turn, including one that carries a design file, SHALL be answered by the Foreman with "Which room is this for?", and no specialist runs.
- Once the conversation has a confirmed room or apartment, a turn that carries a design file goes to the Designer, whatever else the thread holds. A design file sent before the room was confirmed is not imported then; the owner attaches it again once the room is confirmed.
- When the bound piece has no room, or a room outside the conversation's confirmed room or apartment, a turn the Foreman gave to the Designer, Builder, Reviewer or Lighting & materials goes to Intake, which confirms the room for that piece.
- The Builder is never chosen when the thread has no bound piece with a built version.
- The Reviewer is never chosen unless the bound piece's latest version has a screenshot or a render.
- Lighting & materials is never chosen unless the bound piece's latest version has a successful build.
- A thread with no piece and no confirmed brief goes to Intake, unless the owner asks to compose a room while the conversation has a confirmed room, or while the house file holds an approved piece version or a composition in the conversation's room or apartment (the Designer). A confirmed room is enough because a room may be composed with no items.
- A thread with no piece and no confirmed brief SHALL also go to the Designer when the Foreman chose the Designer and the owner's message, or the reply just before it, names a piece in the house file by its package id or its name. This is so that the piece can be revised, rebuilt or given an imported version. Naming that piece SHALL bind the unbound conversation to it when the piece has no conversation yet; when the named piece already has another conversation, the Foreman SHALL say so in plain words and SHALL NOT bind this conversation to it.
- When the conversation is already bound to a piece, naming another house-file piece SHALL NOT change the bound piece and SHALL NOT start design work on the other piece in this conversation.
- The Researcher prices only a bound piece's version.

The fixed questions SHALL be composed by the application, SHALL NOT need a model call, and SHALL be added to the thread's history as the reply. A pending confirmation SHALL resume in the specialist that raised it. The owner never names a specialist and a message cannot force one.

#### Scenario: New wish
- **WHEN** a conversation has no confirmed room and the owner writes "I want a shoe bench"
- **THEN** the reply is "Which room is this for?" and no specialist runs

#### Scenario: New wish naming a room
- **WHEN** a conversation has no confirmed room, `Hall` is in the house file, and the owner writes "a shoe bench for the Hall"
- **THEN** Intake answers

#### Scenario: Room question answered
- **WHEN** the last reply was "Which room is this for?" and the owner answers "the attic, 3 by 4 metres"
- **THEN** Intake answers

#### Scenario: No piece, render asked
- **WHEN** a thread has a confirmed room and no piece and the owner asks for a turntable
- **THEN** Intake or the Designer answers, explaining what must exist first; the Builder is not chosen

#### Scenario: Price question
- **WHEN** a thread's piece has a version and the owner asks what the boards will cost
- **THEN** the Researcher answers with a pricing of that version

#### Scenario: Price question without a room
- **WHEN** a conversation has no confirmed room and the owner asks what an oak board costs at toom
- **THEN** the Researcher answers

#### Scenario: Review asked with nothing rendered
- **WHEN** the bound piece's latest version has no screenshot or render and the owner asks for a check
- **THEN** the Reviewer is not chosen and the reply says what must exist first

#### Scenario: Photoreal detail asked on a built piece
- **WHEN** the bound piece's latest version is built, it is in the conversation's room, and the owner asks for realistic oak and soft lighting
- **THEN** Lighting & materials answers

#### Scenario: Photoreal detail asked with nothing built
- **WHEN** the bound piece has no built version and the owner asks for photoreal detail
- **THEN** Lighting & materials is not chosen and the reply says the piece must be built first

#### Scenario: Design attached in a new thread
- **WHEN** a thread has no piece, no brief and no confirmed room, and the owner sends "import this" with a design file attached
- **THEN** the reply is "Which room is this for?", no specialist runs, and nothing is imported

#### Scenario: Design attached after the room is confirmed
- **WHEN** a thread has no piece and no brief, its confirmed room is `Hall`, and the owner sends "import this" with a design file attached
- **THEN** the Designer answers, not Intake

#### Scenario: Compose request in a new thread
- **WHEN** a thread has no piece and no brief, its confirmed room is `Wohnen`, the house file holds an approved version of `bench` in `Wohnen`, and the owner asks to compose `Wohnen` with it
- **THEN** the Designer answers, not Intake

#### Scenario: Empty room compose request in a new thread
- **WHEN** a thread has no piece and no brief, its confirmed room is `Hall`, nothing is approved and nothing is composed, and the owner asks to compose `Hall` with no furniture
- **THEN** the Designer answers, not Intake

#### Scenario: Revise a named piece from a new thread
- **WHEN** a thread has no piece and no brief, its confirmed room is `Schlafzimmer`, `murphy-bed` has no conversation yet, the Designer's last reply named `murphy-bed` (in `Schlafzimmer`), and the owner answers "Revise it"
- **THEN** the Designer answers, not Intake, and the conversation is bound to `murphy-bed`

#### Scenario: Named piece already has a conversation
- **WHEN** a thread has no piece, its confirmed room is `Schlafzimmer`, `murphy-bed` already has another conversation, and the owner asks to revise `murphy-bed`
- **THEN** the reply says `murphy-bed` already has a conversation, and this thread stays unbound

#### Scenario: No piece named
- **WHEN** a thread has a confirmed room, no piece and no brief, and the owner writes "revise it" without any reply or message naming a piece in the house file
- **THEN** Intake answers

#### Scenario: Two builds named
- **WHEN** a conversation is about `shoe-bench` and the owner writes "make the shoe one wider" also naming `shoe-rack`
- **THEN** the turn stays about `shoe-bench`, no "Which piece do you mean?" reply is given, and no specialist starts work on `shoe-rack` in this conversation

#### Scenario: Bound conversation stays on its piece
- **WHEN** a conversation is about `hall-bench` and the owner writes "make the shoe rack wider" naming `shoe-rack`
- **THEN** the turn stays about `hall-bench` and no specialist starts work on `shoe-rack` in this conversation

#### Scenario: Active build in another room
- **WHEN** the conversation's confirmed room is `Hall`, the bound piece `murphy-bed` is unassigned, and the owner asks for a revision
- **THEN** Intake answers, not the Designer

### Requirement: The Designer creates a piece from a validated spec
The Designer SHALL emit a complete custom-build document, starting from a shipped template and changing only what the brief supports, and call `create_piece` with it and a package id. The shipped templates SHALL include a generic starter, `custom-build`, with one visible cabinet module (carcass, back, shelves and doors), offered to the Designer first; the Designer SHALL start from it unless another shipped template fits the brief better. Every shipped template SHALL validate against the schema and derive at least one cut-list row, except `blank-build`. The document SHALL be validated against the schema before anything else; a valid one is previewed (name, overall size in mm, module count, cut-list rows, hardware lines) and pauses for `yes`. On `yes` the piece and version 1 are recorded and the build starts; on `no` nothing is created and the reason returns to the Designer. A package id already in use SHALL be refused. When the conversation is already bound to a different piece, `create_piece` SHALL be refused naming the bound piece, with no pause.

#### Scenario: Create confirmed
- **WHEN** the owner answers `yes` to a previewed hall bench on an unbound conversation
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

#### Scenario: Second piece refused
- **WHEN** the conversation is about `hall-bench` and the Designer calls `create_piece` for `shelf`
- **THEN** the refusal names `hall-bench`, nothing pauses, and no piece is created
