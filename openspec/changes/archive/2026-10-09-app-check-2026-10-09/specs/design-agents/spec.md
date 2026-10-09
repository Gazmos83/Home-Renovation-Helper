## MODIFIED Requirements

### Requirement: The Designer sees the active build's latest version
Each Designer turn SHALL carry a summary of the active build's latest version, built by the application from that version's stored document. The summary SHALL give:
- the envelope: its width, height and depth in millimetres;
- per module: its id, name, size, position, carcass slot, fixed and adjustable shelves, each front (type, count, opening or hinged side, height when set, hinge item), and its hardware lines (id, item, quantity);
- each wall shelf (id, length, depth, material slot, bracket item, and owner bracket positions when set);
- each extra part by id;
- each material slot with its material and thickness;
- each part override by id.

Only the active build SHALL be summarised; other builds stay one line each. Owner-authored text in the summary SHALL be neutralised. The summary SHALL be labelled as application data, never as an instruction. When the conversation has no active build, or its latest version has no readable document, no summary SHALL be given and the Designer's context SHALL say so.

#### Scenario: Module and fronts visible
- **WHEN** the active build `listening-wall` v7 has module `cabinet` 600×2238×400 mm with 3 shelves and one hinged door
- **THEN** the Designer's context names `cabinet`, its size, "3 shelves" and "1 door (hinge)" for v7

#### Scenario: Envelope visible
- **WHEN** the active build's latest version has an envelope of 2206 × 2238 × 400 mm
- **THEN** the Designer's context gives the envelope as 2206 × 2238 × 400 mm

#### Scenario: Only the active build summarised
- **WHEN** the conversation's builds are `hall-bench` (active) and `shoe-rack`
- **THEN** the Designer's context summarises `hall-bench`'s modules, and `shoe-rack` appears only as its one line

#### Scenario: Delimiter in a module name
- **WHEN** a module's name contains the untrusted-content delimiter
- **THEN** the summary shows it neutralised

#### Scenario: No readable document
- **WHEN** the active build's latest version has no readable document
- **THEN** the Designer's context says the piece's contents could not be read, and no module is listed

## ADDED Requirements

### Requirement: A room is designed without a piece
When the owner asks to design or furnish a room rather than a piece, Intake SHALL confirm the room, or the apartment, through `confirm_room` or `record_plan`. It SHALL then ask what the room should hold: approved pieces of the house file, stand-ins with their sizes, or models of the library, or nothing. It SHALL NOT ask which piece to design, the purpose of a piece, or a piece's size or budget, and it SHALL NOT call `record_brief` for a room-only wish. Once the room is confirmed, its hand-off SHALL offer to compose the room, not to design a piece.

While the conversation has a confirmed room or apartment, a turn whose request the Foreman classifies as composing a room SHALL go to the Designer, whether or not the owner's message names the room, and with no piece and no brief. A request to design a new piece in a conversation with no brief SHALL still go to Intake.

#### Scenario: Room wish
- **WHEN** a conversation has no confirmed room and the owner, after attaching a plan, writes "design the living room"
- **THEN** Intake confirms `Wohnen` and then asks what the room should hold, and no reply asks which piece to design

#### Scenario: Compose without naming the room
- **WHEN** the confirmed room is `Wohnen`, the thread has no piece and no brief, and the owner writes "put a sofa stand-in 2200 by 900 against the window wall"
- **THEN** the Designer answers, not Intake

#### Scenario: Piece wish still goes to Intake
- **WHEN** the confirmed room is `Wohnen`, the thread has no piece and no brief, and the owner writes "I want a new bookshelf"
- **THEN** Intake answers

### Requirement: The Designer gets templates only for a new piece
The Designer's context SHALL carry the custom-build templates only while the conversation has no active build. While an active build exists, the Designer's context SHALL NOT carry any template document, so the only spec figures it sees are the active build's.

#### Scenario: New piece
- **WHEN** the conversation has a confirmed brief and no active build
- **THEN** the Designer's context carries the templates

#### Scenario: Revision turn
- **WHEN** the conversation's active build is `listening-wall` v7
- **THEN** the Designer's context carries v7's summary and no template document

### Requirement: A revision carries the owner's measurements and code checks them
`revise_package` SHALL take, beside the changes, a list of the owner's requested measurements. Each entry SHALL give:
- the owner's words, quoted;
- the module id (or `envelope`, or a wall shelf id);
- the field;
- the target value in millimetres.

The application SHALL check each entry before any confirmation is raised:
- the quote appears in the owner's messages since the last created revision of the piece;
- the quote's length and unit (mm, cm, m) give the target, either as an absolute value, or as a relative value ("wider", "narrower", "taller", "shorter", "deeper", "more", "less", "by") added to or subtracted from the field's value in the latest version;
- the changes set that field to the target.

Every length with a unit in those messages SHALL be covered by an entry. An entry MAY mark its quote as not about the piece (target `none`, for example a room's size); it is accepted when its quote is present, and it covers that length. A failed check SHALL be refused to the Designer naming the quote, the expected value and what the changes set, or naming the uncovered length. No confirmation is raised and no version is created. A request whose figure cannot be tied to one module and field is not checked, and is shown to the owner on the card as usual.

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
- **THEN** the call is refused naming "40 cm" as not covered

#### Scenario: Quote not from the owner
- **WHEN** an entry quotes "90 cm" and no owner message since the last revision contains it
- **THEN** the call is refused naming the quote

#### Scenario: Length not about the piece
- **WHEN** the owner wrote "the room is 4 m wide, make the cabinet 80 cm wide" and the call has the width entry and an entry quoting "4 m wide" with target `none`
- **THEN** the check passes and the confirmation is raised
