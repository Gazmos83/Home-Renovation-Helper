## MODIFIED Requirements

### Requirement: A revision carries the owner's measurements and code checks them
`revise_package` SHALL take, beside the changes, a list of the owner's requested measurements. Each entry SHALL give:
- the owner's words, quoted;
- the module id (or `envelope`, or a wall shelf id);
- the field;
- the target value in millimetres.

The owner's words since the last created revision of the piece SHALL be the owner's messages plus the owner's answers to question forms (`ask_owner`) in that span: each answer given to a question, or the text the owner wrote instead of answering. The text of a question SHALL NOT count as the owner's words.

The application SHALL check each entry before any confirmation is raised:
- the quote appears in the owner's words since the last created revision of the piece;
- the quote's length and unit (mm, cm, m) give the target, either as an absolute value, or as a relative value ("wider", "narrower", "taller", "shorter", "deeper", "more", "less", "by") added to or subtracted from the field's value in the latest version;
- the changes set that field to the target.

Every length with a unit in those words SHALL be covered by an entry. An entry MAY mark its quote as not about the piece (target `none`, for example a room's size or a piece's height on a wall); it is accepted when its quote is present, and it covers that length. A failed check SHALL be refused to the Designer naming the quote, the expected value and what the changes set, or naming the uncovered length. A refusal for an uncovered length or a quote not found SHALL also quote the owner's sentence that holds the length, so the Designer can quote it exactly. No confirmation is raised and no version is created. A request whose figure cannot be tied to one module and field is not checked, and is shown to the owner on the card as usual.

#### Scenario: Absolute width honoured
- **WHEN** the owner wrote "make the cabinet 80 cm wide" and the call's entry quotes it with `cabinet`, `width`, 800, and the changes set `cabinet` width to 800
- **THEN** the confirmation is raised with "cabinet: width 600 → 800"

#### Scenario: Invented value refused
- **WHEN** the owner wrote "make the cabinet 80 cm wide" and the changes set `cabinet` width to 750
- **THEN** the call is refused naming "80 cm wide", 800 expected and 750 set, and no confirmation is raised

#### Scenario: Relative change resolved
- **WHEN** `cabinet` is 600 mm wide, the owner wrote "5 cm wider", and the changes set `cabinet` width to 650
- **THEN** the check passes and the confirmation is raised

#### Scenario: Measurement left out
- **WHEN** the owner wrote "80 cm wide and 40 cm deep" and the call covers only the width
- **THEN** the call is refused naming "40 cm" as not covered and quoting "80 cm wide and 40 cm deep"

#### Scenario: Quote not from the owner
- **WHEN** an entry quotes "90 cm" and no owner message or form answer since the last revision contains it
- **THEN** the call is refused naming the quote

#### Scenario: Length not about the piece
- **WHEN** the owner wrote "the room is 4 m wide, make the cabinet 80 cm wide" and the call has the width entry and an entry quoting "4 m wide" with target `none`
- **THEN** the check passes and the confirmation is raised

#### Scenario: Width given in a question form
- **WHEN** the Designer asked "How wide is the lamellen-kommode, so the sideboard can match it?", the owner answered "1350 mm", and the call's entry quotes "1350 mm" with `cabinet`, `width`, 1350 and the changes set it
- **THEN** the check passes and the confirmation is raised

#### Scenario: A figure in the question text is not the owner's
- **WHEN** a form question reads "Should it stay 450 mm deep?" and the owner answered "Yes", and an entry quotes "450 mm"
- **THEN** the call is refused naming "450 mm" as not in the owner's words

## ADDED Requirements

### Requirement: Hardware words alone do not make a revision an engineering turn
A message that asks to change the bound piece SHALL NOT become an engineering turn only because it names hardware or a cabinet kind: hanger, hinge, drawer, runner, wall cabinet, base cabinet, kitchen cabinet, worktop, countertop, their German forms, or a kitchen hardware intent. It SHALL become an engineering turn when it also holds a load, capacity, safety, stability, anchorage, deflection or span term, or a weight to hold. Any other message SHALL be classified as before.

The code's engineering terms SHALL include shelf span and sag wording: "allowable … span", "shelf span", "sag" and "sagging" (and "durchhängen").

#### Scenario: Adding a wall hanger
- **WHEN** the conversation has a bound piece and the owner writes "Yes, please add a wall hanger to the sideboard"
- **THEN** the turn is not an engineering turn and the Designer restates the change as usual

#### Scenario: Hanger with a load
- **WHEN** the owner writes "add a wall hanger that holds 30 kg"
- **THEN** the turn is an engineering turn

#### Scenario: Shelf span question
- **WHEN** the owner writes "What's the allowable shelf span for particle boards?"
- **THEN** the code marks it an engineering turn, whatever the routing model flagged

### Requirement: A model-only engineering flag never replaces an ordinary answer
When a turn is an engineering turn only because the routing model flagged it, and the owner's message holds no engineering term by code, a specialist answer that the engineering format rejects SHALL NOT stand as the whole reply. The same specialist SHALL answer that turn once more as an ordinary turn, with the ordinary tools and notes and no engineering answer note, and its answer SHALL be the reply. A turn with an engineering term by code keeps the fixed status sentence on a rejected answer.

#### Scenario: Space question flagged by the model
- **WHEN** the routing model flags "How much space is there between the murphy bed and wall 1?" as engineering and the specialist's engineering answer is rejected
- **THEN** the owner gets an ordinary answer about the space, not only "Not verified: no engineering check is available …"

#### Scenario: Load question keeps the status
- **WHEN** the owner asks "Is the shelf safe for 40 kg?" and the engineering answer is rejected
- **THEN** the reply is only the fixed status sentence

### Requirement: A no to the room question is a decline
When the last reply before the owner's message was "Which room is this for?", the message names no room or apartment of the house file and carries no plan or photo, and its first word is a no-word ("no", "none", "without", "nein", "kein", "keinen"), the application SHALL save the conversation's room as declined, as for a "no" to "Would you like to view this piece in a room?". Neither room question SHALL be asked again in that conversation; the owner can still name a room later.

#### Scenario: No room for now
- **WHEN** the reply was "Which room is this for?" and the owner writes "No room for now, design it without one."
- **THEN** the room is saved as declined, and the next turn "Yes, go on with the design." is routed without either room question

#### Scenario: A room named after the question
- **WHEN** the reply was "Which room is this for?" and the owner writes "Wohnen"
- **THEN** nothing is declined and the room is confirmed as before

### Requirement: The saved placement is in the Designer's and the Builder's context
When the bound piece's latest version has a saved placement in the conversation's confirmed room, the Designer's and the Builder's notes SHALL state it on every turn: the room, the wall as the owner numbers it, the distance from the wall's left end, and the height of the piece's underside above the floor when it is hung. A specialist SHALL NOT ask the owner for a placement figure the note states.

#### Scenario: Hung sideboard placement remembered
- **WHEN** sideboard-1200 version 2 is saved on wall 2 of Wohnen, 0 mm from the left end, hung at 1700 mm, and the owner later writes "Build it and show it in the room"
- **THEN** the Builder's note states wall 2, 0 mm and 1700 mm, and no specialist asks for the height again
