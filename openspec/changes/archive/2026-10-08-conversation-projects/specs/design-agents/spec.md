## MODIFIED Requirements

### Requirement: The Foreman routes each turn to one specialist
Each turn SHALL be handled by exactly one specialist (Intake, Designer, Builder, Researcher, Reviewer or Lighting & materials), chosen by the Foreman from the conversation and the house file, or answered by the Foreman with one of its two fixed questions below. Application rules bound the choice, in this order:
- A question the Researcher answers (a price, a product, a guideline) goes to the Researcher, with or without a confirmed room.
- When the owner's message, or the reply just before it, names two or more builds of the conversation by package id or name, the Foreman SHALL answer "Which piece do you mean?" listing those builds, and no specialist runs.
- While the conversation has no confirmed room or apartment, a turn that carries a plan or photo, names a room or apartment of the house file, or answers the Foreman's room question goes to Intake. Any other turn, including one that carries a design file, SHALL be answered by the Foreman with "Which room is this for?", and no specialist runs.
- Once the conversation has a confirmed room or apartment, a turn that carries a design file goes to the Designer, whatever else the thread holds. A design file sent before the room was confirmed is not imported then; the owner attaches it again once the room is confirmed.
- When the active build has no room, or a room outside the conversation's confirmed room or apartment, a turn the Foreman gave to the Designer, Builder, Reviewer or Lighting & materials goes to Intake, which confirms the room for that build.
- The Builder is never chosen when the thread has no bound piece with a built version.
- The Reviewer is never chosen unless the bound piece's latest version has a screenshot or a render.
- Lighting & materials is never chosen unless the bound piece's latest version has a successful build.
- A thread with no piece and no confirmed brief goes to Intake, unless the owner asks to compose a room while the house file holds an approved piece version or a composition in the conversation's room or apartment (the Designer).
- A thread with no piece and no confirmed brief SHALL also go to the Designer when the Foreman chose the Designer and the owner's message, or the reply just before it, names a piece in the house file by its package id or its name. This is so that the piece can be revised, rebuilt or given an imported version. A named piece that is not yet one of the conversation's builds joins them and becomes the active build.
- The Researcher prices only a bound piece's version.

The two fixed questions SHALL be composed by the application, SHALL NOT need a model call, and SHALL be added to the thread's history as the reply. A pending confirmation SHALL resume in the specialist that raised it. The owner never names a specialist and a message cannot force one.

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

#### Scenario: Revise a named piece from a new thread
- **WHEN** a thread has no piece and no brief, its confirmed room is `Schlafzimmer`, the Designer's last reply named `murphy-bed` (in `Schlafzimmer`), and the owner answers "Revise it"
- **THEN** the Designer answers, not Intake, and `murphy-bed` is the conversation's active build

#### Scenario: No piece named
- **WHEN** a thread has a confirmed room, no piece and no brief, and the owner writes "revise it" without any reply or message naming a piece in the house file
- **THEN** Intake answers

#### Scenario: Two builds named
- **WHEN** a conversation's builds are `shoe-rack` and `shoe-bench` and the owner writes "make the shoe one wider"
- **THEN** the reply asks which piece is meant, naming `shoe-rack` and `shoe-bench`, and no specialist runs

#### Scenario: Active build in another room
- **WHEN** the conversation's confirmed room is `Hall`, the active build `murphy-bed` is unassigned, and the owner asks for a revision
- **THEN** Intake answers, not the Designer

### Requirement: Intake turns a wish into confirmed numbers
Intake SHALL collect the brief — the piece's purpose, its rough size and heights, style and budget, and the room (by name, or its measurements) when the owner gives one — ask for what is missing without inventing a figure, and propose the confirmed numbers through `record_brief`, which pauses for the owner's `yes`. A brief that names no room SHALL take the conversation's confirmed room; a brief may still be confirmed with no room at all, but the Designer SHALL NOT start while the conversation has no confirmed room. A room that is given SHALL be validated as before. On `yes` the room (when given), preferences and the brief are written to the house file, and a room named in the brief becomes the conversation's confirmed room; on `no` nothing is written and the reason returns to Intake.

#### Scenario: Numbers confirmed
- **WHEN** the owner confirms a hall 1200 mm wide and 2400 mm high with a 400 EUR budget
- **THEN** the house file holds the room and `budget_eur`, the hall is the conversation's confirmed room, and the reply offers to design the piece

#### Scenario: Missing height
- **WHEN** the owner has not said how high the piece may be
- **THEN** Intake asks for the height and proposes no numbers

#### Scenario: Brief without a room
- **WHEN** the conversation has no confirmed room and the owner wants a listening wall about 2200 mm wide and 2200 mm tall in light oak for 900 EUR and names no room
- **THEN** `record_brief` previews the purpose, size, style and budget with "Room: not given yet", and on `yes` the brief is stored with no room and no room is written

#### Scenario: Designer follows a room-less brief
- **WHEN** a thread's brief was confirmed without a room, the conversation has no confirmed room, and the owner asks to design the piece
- **THEN** the reply is "Which room is this for?" and the Designer does not run

#### Scenario: Brief takes the conversation's room
- **WHEN** the conversation's confirmed room is `Hall` and the owner confirms a brief that names no room
- **THEN** the stored brief names `Hall`

## ADDED Requirements

### Requirement: Intake confirms the conversation's room
Intake SHALL confirm a conversation's room or apartment through `confirm_room`, which names a room or an apartment of the house file and, optionally, one of the conversation's builds to move into that room. It SHALL pause for the owner's `yes` with a summary of the stored measurements (size, ceiling height, openings; for an apartment each room's size) and, when a build is named, the build and the room it moves from. On `yes` the room or apartment becomes the conversation's confirmed room, replacing any earlier one, and a named build is moved into the room. On `no` nothing changes and the reason returns to Intake. A room or apartment not in the house file, or a build outside the conversation, SHALL be refused naming it with no pause, so Intake can ask for the measurements through `record_brief` or `record_plan`. A build SHALL be moved only into a room, never into an apartment as a whole. A confirmed `record_plan` SHALL make its apartment the conversation's confirmed apartment. A `record_brief` that names a stored room without new measurements SHALL show that room's stored size, ceiling height and openings in its summary, so its `yes` confirms them.

#### Scenario: Stored room offered and confirmed
- **WHEN** `Hall` is in the house file and the owner, asked which room, answers "the hall"
- **THEN** `confirm_room` shows the hall's stored size, ceiling height and openings, and on `yes` the conversation's confirmed room is `Hall`

#### Scenario: Declined
- **WHEN** the owner answers `no` to the hall's stored measurements with "the door moved"
- **THEN** the conversation still has no confirmed room and Intake continues with the reason

#### Scenario: Room switched
- **WHEN** the conversation's confirmed room is `Hall` and the owner confirms `Wohnen`
- **THEN** the conversation's confirmed room is `Wohnen` and the builds already made keep their rooms

#### Scenario: Build moved
- **WHEN** the owner confirms moving the build `shoe-rack` from `Hall` to `Wohnen`
- **THEN** `shoe-rack` is in `Wohnen` and the conversation's confirmed room is `Wohnen`

#### Scenario: Brief names a stored room
- **WHEN** Intake proposes a brief for `Hall`, which the house file holds, without new measurements
- **THEN** the summary shows the hall's stored size, ceiling height and openings, and on `yes` the conversation's confirmed room is `Hall`

#### Scenario: Unknown room
- **WHEN** Intake names `Attic` and no such room is recorded
- **THEN** the refusal names `Attic`, nothing pauses, and nothing changes

### Requirement: A new piece is recorded in the conversation's room
A confirmed `create_piece` SHALL record the piece in the brief's room when the brief names one, otherwise in the conversation's confirmed room. When the conversation's confirmed scope is an apartment and the brief names none of its rooms, `create_piece` SHALL be refused, asking which room of the apartment the piece is for, with no pause. A confirmed design import SHALL record the piece in the conversation's confirmed room; it never runs without one (the room question comes first), and with a confirmed apartment it SHALL be refused like `create_piece`, asking which room of the apartment the piece is for.

#### Scenario: Piece in the confirmed room
- **WHEN** the conversation's confirmed room is `Hall` and the owner confirms the new piece `shoe-bench`
- **THEN** the house file holds `shoe-bench` in `Hall`

#### Scenario: Apartment without a room
- **WHEN** the conversation's confirmed apartment is `Wohnung` and the Designer proposes a piece whose brief names no room
- **THEN** the refusal asks which room of `Wohnung` the piece is for, and nothing pauses

#### Scenario: Imported piece in the confirmed room
- **WHEN** the conversation's confirmed room is `Hall` and the owner confirms importing a design file as the new piece `hall-cabinet`
- **THEN** the house file holds `hall-cabinet` in `Hall`
