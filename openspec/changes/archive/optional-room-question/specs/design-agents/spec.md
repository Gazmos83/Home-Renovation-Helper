## MODIFIED Requirements

### Requirement: The Foreman routes each turn to one specialist
Each turn SHALL be handled by exactly one specialist (Intake, Designer, Builder, Researcher, Reviewer or Lighting & materials), chosen by the Foreman from the conversation and the house file, or answered by the Foreman with one of its fixed questions below. The one exception is the hand-off of a pending design file below, where Intake is followed by the Designer in the same turn. Application rules bound the choice, in this order:
- A question the Researcher answers (a price, a product, a guideline) goes to the Researcher, with or without a confirmed room.
- A help question (how to use the app: its pages, conversations, rooms, renders, files or the design file template, and not a request to design, build, render, review or price something) goes to Intake, with or without a confirmed room, and before the room question below. A turn that carries a plan, a photo or a design file is never a help question. A help question does not change the conversation's confirmed room or bound piece.
- While the conversation has no confirmed room or apartment and has not declined one, a turn that carries a plan or photo, names a room or apartment of the house file, or answers the Foreman's "Which room is this for?" goes to Intake. Any other turn, including one that carries a design file, SHALL be answered by the Foreman with "Would you like to view this piece in a room?", and no specialist runs.
- The application SHALL read the owner's answer to "Would you like to view this piece in a room?", with no model call. An answer that names a room or apartment of the house file is a yes with that room and goes to Intake. Otherwise, an answer whose first word is "yes", "ja", "yeah", "sure", "ok" or "okay" (any case) SHALL be answered by the Foreman with "Which room is this for?", and no specialist runs. Any other answer is a no.
- A no SHALL record that the conversation declined a room, and the Foreman SHALL NOT ask either room question again in that conversation. The owner can still give a room later by naming it, or by sending a plan or photo, which goes to Intake as above. On the turn of the no, when the conversation has no piece and an owner message carries a design file, the Designer SHALL import the newest such file, as on the turn that confirms a room. Otherwise the turn is routed by the rules below as if a room were confirmed.
- Once the conversation has a confirmed room or apartment, or has declined one, a turn that carries a design file goes to the Designer, whatever else the thread holds.
- A design file sent before the room was confirmed is not imported then. When an Intake turn confirms the conversation's room or apartment (it had none when the turn began), the conversation has no piece, and an owner message in the conversation carries a design file, the same turn SHALL go on to the Designer once Intake has finished. The Designer SHALL import the newest such design file, and the owner SHALL be shown its import preview and SHALL answer yes or no as for an attached file. This hand-off SHALL be decided by the application, not by a model. It SHALL happen only on the turn that confirms the room, so a later turn does not offer the file again; attaching it again still imports it. Intake SHALL NOT tell the owner that an attached design file cannot be imported.
- When the conversation has not declined a room and the bound piece has no room, or a room outside the conversation's confirmed room or apartment, a turn the Foreman gave to the Designer, Builder, Reviewer or Lighting & materials goes to Intake, which confirms the room for that piece.
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
- **THEN** the reply is "Would you like to view this piece in a room?" and no specialist runs

#### Scenario: Owner wants the piece in a room
- **WHEN** the last reply was "Would you like to view this piece in a room?" and the owner answers "yes"
- **THEN** the reply is "Which room is this for?" and no specialist runs

#### Scenario: Owner names the room straight away
- **WHEN** the last reply was "Would you like to view this piece in a room?", `Wohnen` is in the house file, and the owner answers "yes, Wohnen"
- **THEN** Intake answers

#### Scenario: Owner declines a room
- **WHEN** the last reply was "Would you like to view this piece in a room?" after "I want a shoe bench", and the owner answers "no"
- **THEN** the conversation records that it declined a room, Intake answers about the shoe bench, and no room question is asked

#### Scenario: Not asked again
- **WHEN** a conversation declined a room and the owner later writes "make it 10 cm wider"
- **THEN** neither room question is asked and the turn is routed by the other rules

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
- **THEN** the reply is "Would you like to view this piece in a room?", no specialist runs, and nothing is imported

#### Scenario: Design attached, room declined
- **WHEN** a thread has no piece, no brief and no confirmed room, the owner sent "import this" with `lamellen-kommode.json` attached, was asked "Would you like to view this piece in a room?", and answers "no"
- **THEN** in the same turn the Designer shows the import preview for `lamellen-kommode.json`; nothing is created before the owner's yes

#### Scenario: Design attached before the room, imported once it is confirmed
- **WHEN** a thread has no piece, no brief and no confirmed room, the owner sent "I'd like to view this dresser" with `kommode-harmony.json` attached, answered "Would you like to view this piece in a room?" with "yes", was asked "Which room is this for?", and answers "Wohnen" and says yes to Intake's room confirmation
- **THEN** the conversation works in `Wohnen`, and in the same turn the Designer shows the import preview for `kommode-harmony.json`; nothing is created before the owner's yes

#### Scenario: Pending design import declined
- **WHEN** a room confirmation has handed `kommode-harmony.json` to the Designer and the owner answers no to the import preview
- **THEN** nothing is imported, and the owner's next message without an attachment does not show the preview again

#### Scenario: Room confirmed in a thread that already has a piece
- **WHEN** a thread bound to `hall-bench` had a design file attached earlier, and an Intake turn confirms the conversation's room
- **THEN** the turn ends with Intake and the Designer does not run

#### Scenario: Room confirmation declined
- **WHEN** a design file is pending and the owner answers no to Intake's room confirmation
- **THEN** no room is confirmed, the Designer does not run, and nothing is imported

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

#### Scenario: Unassigned piece in a conversation that declined a room
- **WHEN** a conversation declined a room, its bound piece `lamellen-kommode` is unassigned, and the owner asks for a revision
- **THEN** the Designer answers, not Intake

#### Scenario: Help question in a new thread
- **WHEN** a conversation has no confirmed room and the owner writes "How do I use the design template?"
- **THEN** Intake answers, and the reply is neither "Would you like to view this piece in a room?" nor "Which room is this for?"

#### Scenario: Help question in a bound thread
- **WHEN** a conversation is about `hall-bench` and the owner asks "What is the difference between a draft and a final render?"
- **THEN** Intake answers, and the conversation stays bound to `hall-bench`

#### Scenario: Design file is not a help question
- **WHEN** a conversation has no confirmed room and the owner attaches a design file asking "how does this work?"
- **THEN** the reply is "Would you like to view this piece in a room?" and no specialist runs

### Requirement: Intake turns a wish into confirmed numbers
Intake SHALL collect the brief — the piece's purpose, its rough size and heights, style and budget, and the room (by name, or its measurements) when the owner gives one — ask for what is missing without inventing a figure, and propose the confirmed numbers through `record_brief`, which pauses for the owner's `yes`. A brief that names no room SHALL take the conversation's confirmed room; a brief may still be confirmed with no room at all, but the Designer SHALL NOT start while the conversation has no confirmed room, unless the conversation declined a room. A room that is given SHALL be validated as before. On `yes` the room (when given), preferences and the brief are written to the house file, and a room named in the brief becomes the conversation's confirmed room; on `no` nothing is written and the reason returns to Intake.

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
- **WHEN** a thread's brief was confirmed without a room, the conversation has no confirmed room and has not declined one, and the owner asks to design the piece
- **THEN** the reply is "Would you like to view this piece in a room?" and the Designer does not run

#### Scenario: Designer follows a brief in a conversation that declined a room
- **WHEN** a thread's brief was confirmed without a room, the conversation declined a room, and the owner asks to design the piece
- **THEN** the Designer answers

#### Scenario: Brief takes the conversation's room
- **WHEN** the conversation's confirmed room is `Hall` and the owner confirms a brief that names no room
- **THEN** the stored brief names `Hall`

### Requirement: A new piece is recorded in the conversation's room
A confirmed `create_piece` SHALL record the piece in the brief's room when the brief names one, otherwise in the conversation's confirmed room, and with neither, when the conversation declined a room, with no room (unassigned). When the conversation's confirmed scope is an apartment and the brief names none of its rooms, `create_piece` SHALL be refused, asking which room of the apartment the piece is for, with no pause. A confirmed design import SHALL record the piece in the conversation's confirmed room, or with no room when the conversation declined one; it never runs while the room question is still open, and with a confirmed apartment it SHALL be refused like `create_piece`, asking which room of the apartment the piece is for.

#### Scenario: Piece in the confirmed room
- **WHEN** the conversation's confirmed room is `Hall` and the owner confirms the new piece `shoe-bench`
- **THEN** the house file holds `shoe-bench` in `Hall`

#### Scenario: Apartment without a room
- **WHEN** the conversation's confirmed apartment is `Wohnung` and the Designer proposes a piece whose brief names no room
- **THEN** the refusal asks which room of `Wohnung` the piece is for, and nothing pauses

#### Scenario: Imported piece in the confirmed room
- **WHEN** the conversation's confirmed room is `Hall` and the owner confirms importing a design file as the new piece `hall-cabinet`
- **THEN** the house file holds `hall-cabinet` in `Hall`

#### Scenario: Imported piece without a room
- **WHEN** the conversation declined a room and the owner confirms importing a design file as the new piece `lamellen-kommode`
- **THEN** the house file holds `lamellen-kommode` with no room, shown as "No room" on the Pieces page
