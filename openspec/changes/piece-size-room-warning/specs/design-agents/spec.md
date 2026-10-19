## MODIFIED Requirements

### Requirement: Intake turns a wish into confirmed numbers
Intake SHALL collect the brief — the piece's purpose, its rough size and height, style and budget, the room (by name, or its measurements) when the owner gives one, and the highest the piece may be only when the owner gives it — ask for what is missing without inventing a figure, never ask for the highest the piece may be, and propose the confirmed numbers through `record_brief`, which pauses for the owner's `yes`. A brief that names no room SHALL take the conversation's confirmed room; a brief may still be confirmed with no room at all, but the Designer SHALL NOT start while the conversation has no confirmed room, unless the conversation declined a room. A room that is given SHALL be validated as before. On `yes` the room (when given), preferences and the brief are written to the house file, and a room named in the brief becomes the conversation's confirmed room; on `no` nothing is written and the reason returns to Intake.

#### Scenario: Numbers confirmed
- **WHEN** the owner confirms a hall 1200 mm wide and 2400 mm high with a 400 EUR budget
- **THEN** the house file holds the room and `budget_eur`, the hall is the conversation's confirmed room, and the reply offers to design the piece

#### Scenario: Missing height
- **WHEN** the owner has not said how high the piece will be
- **THEN** Intake asks for the piece's height and proposes no numbers

#### Scenario: No limit given
- **WHEN** the owner has given the purpose, a rough size of 1200 × 400 × 900 mm, the style and the budget, and no highest height
- **THEN** Intake proposes the brief through `record_brief` without asking for the highest the piece may be, and the stored brief has no limit

#### Scenario: Brief without a room
- **WHEN** the conversation has no confirmed room and the owner wants a listening wall about 2200 mm wide and 2200 mm tall in light oak for 900 EUR and names no room
- **THEN** `record_brief` previews the purpose, size, style and budget with "Room: not given yet", and on `yes` the brief is stored with no room and no room is written

#### Scenario: Designer follows a room-less brief
- **WHEN** a thread's brief was confirmed without a room, the conversation has no confirmed room and has not declined one, and the owner asks to design the piece
- **THEN** the reply is "Would you like to view this piece in a room?" and the Designer does not run

#### Scenario: Designer follows a brief in a conversation that declined a room
- **WHEN** a thread's brief was confirmed without a room, the conversation declined a room, and the owner asks to design the piece
- **THEN** the Designer answers

#### Scenario: Brief takes the conversation's room
- **WHEN** the conversation's confirmed room is `Hall` and the owner confirms a brief that names no room
- **THEN** the stored brief names `Hall`
