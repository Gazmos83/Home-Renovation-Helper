# design-agents Specification

## Purpose
Defines the Foreman and its three specialists for the design loop: how a turn is routed, what Intake, the Designer and the Builder may do, which actions wait for the owner, how a spec the schema cannot express is refused and recorded, and how every render goes through the guard.

## Requirements

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
- A thread with no piece and no confirmed brief goes to Intake, unless the owner asks to compose a room while the conversation has a confirmed room, or while the house file holds an approved piece version or a composition in the conversation's room or apartment (the Designer). A confirmed room is enough because a room may be composed with no items.
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

#### Scenario: Empty room compose request in a new thread
- **WHEN** a thread has no piece and no brief, its confirmed room is `Hall`, nothing is approved and nothing is composed, and the owner asks to compose `Hall` with no furniture
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

### Requirement: A spec the schema cannot express is refused and recorded
When the Designer's document names a field the schema does not define, `create_piece` or `revise_package` SHALL refuse naming the field, SHALL record a generator-extension request with the field and the owner's words, and the Designer SHALL tell the owner plainly that the change is not expressible yet and has been recorded — never offering to write Blender code instead.

#### Scenario: Bevelled edge
- **WHEN** the owner asks for a bevelled front edge and the document carries `bevel_mm`
- **THEN** the reply says the bevel cannot be expressed yet and was recorded, a request naming `bevel_mm` exists, and no version was created

### Requirement: The Designer revises a piece from stated changes
`revise_package` SHALL take the piece's package id and a bounded set of changes — the name, the envelope, a material slot, per module (by its id) any field, modules to add or remove, extra parts, part overrides — apply them to a copy of the latest version's document, refuse naming an unknown module or part id, validate the result, preview the change lines and pause for `yes`. On `yes` the next version is recorded as revised from the latest and built; the earlier version's folder and record are untouched. Only the round's first revision call is offered; a second in the same round is answered as not created.

#### Scenario: Shelves changed
- **WHEN** the owner says "three shelves in the cabinet" and confirms
- **THEN** version 2 exists with "cabinet: shelves 2 → 3" and version 1 is unchanged

#### Scenario: Unknown module
- **WHEN** the change names module `drawers` which the piece does not have
- **THEN** it is refused naming `drawers` and listing the piece's modules, and no confirmation is raised

### Requirement: The cut list is derived without rendering
`cut_list` SHALL return a version's derived parts (id, qty, length, width, thickness, material) and hardware lines from its stored document and its saved hardware inputs, with totals, and its drilling list per part with the drilling-work counts, without starting any Blender process. A ranged position SHALL be reported as its range and a position given as a rule as its words, never as a single number. When the drilling list is incomplete, `cut_list` SHALL say so and name every missing value; for a version with no saved inputs it SHALL say that drilling was not calculated.

#### Scenario: Parts listed
- **WHEN** the Designer calls `cut_list` for `hall-bench` version 1
- **THEN** the result lists every derived part with its dimensions and no process is started

#### Scenario: Drilling incomplete
- **WHEN** the Designer calls `cut_list` for a version whose hinge data sheet lacks the cup edge distance
- **THEN** the result lists the drilling positions it has, says the drilling list is incomplete, and names "cup edge distance"

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

### Requirement: The Builder builds and renders only through the guard
`blender_build` SHALL build a version that has not succeeded yet, wait for it within the Blender timeout, and report the outcome with the screenshot route; a version already built SHALL be reported as such without rebuilding. `render_turntable` SHALL require a tier, SHALL refuse raw frame, resolution or engine values by name, SHALL render a still or a turntable of a version alone or placed with a `room_fit` placement, and SHALL start the run and report the estimate for `draft` and `preview`; for `final` it SHALL pause with the estimate and run only on `yes`. When a render starts, the reply SHALL give the estimate and SHALL NOT give a viewer route: for a piece version it SHALL say that a Review button appears in this chat when the render finishes, and for a shell or composition that a notice appears in this chat. The Builder SHALL never write or run Blender Python.

#### Scenario: Draft turntable
- **WHEN** the owner asks for a draft turntable of a built piece
- **THEN** the run is started at tier `draft` and the reply gives the estimate in plain terms and says a Review button appears in this chat when it finishes, with no viewer route

#### Scenario: Final paused
- **WHEN** the owner asks for a final render
- **THEN** the reply carries a pending confirmation with the estimate and nothing has started

#### Scenario: Raw frames refused
- **WHEN** the Builder's call carries `frames: 100`
- **THEN** it is refused naming `frames` and no process starts

### Requirement: Intake reads attached plans and photos
When a turn attaches a blueprint or photo, Intake SHALL read from it only what it can see — the scale (from a dimension line, a printed area or a known door width), the room outlines, ceiling height when written, openings with their walls and offsets — and SHALL say which figures were read and which are assumed defaults, asking for any it cannot read. Intake SHALL use `record_plan` for an apartment of several rooms and `record_brief` for a single room; a photo SHALL inform materials, light and position, never a dimension the plan contradicts.

#### Scenario: Blueprint without a ceiling height
- **WHEN** the owner attaches a blueprint that shows no ceiling height
- **THEN** Intake proposes no plan until the owner gives the height, or states the 2500 mm default it would use and asks the owner to confirm it

#### Scenario: Photo contradicts the plan
- **WHEN** a photo suggests a wider window than the plan shows
- **THEN** Intake keeps the plan's width and mentions the difference to the owner

### Requirement: Room corrections go to Intake
A message that corrects or adds to a room's measurements, corners, corner angles, ceiling height, wall thickness or openings, or that attaches a new or revised plan of a room, SHALL be handled by Intake, also when the thread has a confirmed brief or a bound piece. Intake SHALL propose the corrected room through `record_brief` or `record_plan` and the owner's `yes`, as for a first brief. A change to the piece itself (its size, modules, shelves, fronts or materials) SHALL stay with the Designer.

#### Scenario: Corner angle corrected after the brief
- **WHEN** a thread has a confirmed brief for the living room and the owner writes "bottom wall/left wall corner = 76°"
- **THEN** Intake answers and proposes the corrected room for confirmation

#### Scenario: Revised plan attached after a piece exists
- **WHEN** the bound piece has a version and the owner attaches `blueprint_revision.png` saying it is the source of truth for the room
- **THEN** Intake answers

#### Scenario: Piece change stays with the Designer
- **WHEN** a thread has a confirmed brief and the owner writes "make it 2206 mm wide"
- **THEN** the Designer answers

### Requirement: A tool outside the specialist's set is refused naming its owner
When a specialist calls a tool it has not bound, nothing SHALL run and the call's result SHALL name the tool and either the specialist or specialists whose instruction header names it, or, when the specialist's own header names it but its plugin is switched off for the thread, that the tool is switched off in this conversation's tools. The result SHALL state that nothing was done. Every specialist's instructions SHALL tell it to say so plainly to the owner (that nothing was saved or changed, and why) and never to describe the refusal as the tool failing or refusing an update.

#### Scenario: Designer calls Intake's tool
- **WHEN** the Designer calls `record_brief`
- **THEN** nothing is saved, the call's result names `record_brief` and Intake and says nothing was done, and no confirmation is raised

#### Scenario: Own tool switched off
- **WHEN** the Designer calls `cut_list` on a thread where the `cut_list` plugin is switched off
- **THEN** nothing runs and the result says `cut_list` is switched off in this conversation's tools

### Requirement: No specialist promises to report back after the turn
A turn SHALL end with its reply, and no specialist SHALL message the owner afterwards. No specialist's instructions SHALL let it promise to tell the owner later when a build, a render or a review finishes. The only message after a turn SHALL be the render notice that code posts when a render started in the conversation finishes or fails; it is never written by a model. The Builder and the Designer SHALL say that a started build's status shows in the conversation's Project panel and can be asked for in a later message.

#### Scenario: Owner asks to be told when the build is done
- **WHEN** a build has started and the owner asks "Will you tell me when the build is complete?"
- **THEN** the reply says the Project panel shows the build's status and that the owner can ask again, and it does not promise a later message

#### Scenario: Render notice is posted by code
- **WHEN** a draft turntable started in the conversation finishes after the turn has ended
- **THEN** a render notice appears in the conversation, posted by code, and no specialist runs or writes a message

### Requirement: The Designer composes a room
`compose_room` SHALL take a full composition: its scope (a room, or an apartment) and its list of items with their placements. For a room the list SHALL be allowed to be empty, which composes the room alone. It SHALL validate the composition, then pause for the owner's `yes` with a summary. The summary SHALL list each item with its size and placement, or say that the room is composed with no items, any design-rule warnings, and, when a composition already exists for that scope, the items added, moved and removed relative to its latest version. Only `yes` SHALL create the version and start its headless build. A refusal (unknown room, unapproved version, model not ready, invalid placement, an apartment with no items) SHALL be returned to the Designer without a pause, so the Designer can state it to the owner in plain words. The Designer SHALL never write or run Blender Python.

#### Scenario: Confirmed composition
- **WHEN** the owner asks to see the approved listening wall in `Wohnen` with a sofa stand-in, and answers `yes` to the summary
- **THEN** `Wohnen` v1 is created and its build is started, and the reply says so

#### Scenario: Empty room confirmed
- **WHEN** the owner asks for a composition of `Hall` with no furniture and answers `yes` to a summary saying the room is composed with no items
- **THEN** `Hall` v1 is created with no items and its build is started, and the reply says so

#### Scenario: Last item removed
- **WHEN** `Hall` v1 holds one stand-in and the owner confirms `Hall` with no items
- **THEN** the summary lists that stand-in as removed, and on `yes` `Hall` v2 is created with no items

#### Scenario: Declined
- **WHEN** the owner answers `no`
- **THEN** no version is created and nothing is built

#### Scenario: Unapproved piece
- **WHEN** the Designer proposes a piece version that is not approved
- **THEN** no confirmation is shown, and the reply names the version and says it must be approved first

### Requirement: The Builder renders a composition through the guard
`render_turntable` SHALL accept exactly one target: a piece, a shell, or a composition (its scope name and, optionally, a version, the latest by default). A composition target SHALL follow the same tier, refusal, estimate and `final` approval rules as the other targets. It SHALL refuse a composition version whose build has not succeeded, saying it must be built first. When the composition has a placed version that is no longer approved, the reply SHALL say so. A composition with a built version SHALL give the Builder something to work on, in the same way a built piece or shell does.

#### Scenario: Draft of a room
- **WHEN** the owner asks for a draft turntable of `Wohnen`
- **THEN** the run starts at tier `draft` on the latest built version, and the reply gives the estimate and says a notice appears in this chat when it finishes, with no viewer route

#### Scenario: Two targets
- **WHEN** a call names both a piece and a composition
- **THEN** it is refused saying to name exactly one target

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

### Requirement: Intake and the Designer ask questions through a form
Intake and the Designer SHALL have an `ask_owner` tool, from a plugin that cannot be toggled off, that takes one to eight questions, each with its text (1–200 characters), an optional unit and optional choices (two to eight, each 1–60 characters). A valid call SHALL pause the turn with the questions pending; an invalid call SHALL be refused to the model with the reason and pause nothing. The answers (or the owner's message when the set is declined) SHALL return to the specialist as the tool's result in the same turn. Only one pending item SHALL be raised per round: an `ask_owner` call in a round that already pauses on a confirmation SHALL be refused as not run.

#### Scenario: Missing figures
- **WHEN** Intake lacks the ceiling height and the budget
- **THEN** it calls `ask_owner` with both questions, with units mm and EUR, and the turn pauses

#### Scenario: Too many questions
- **WHEN** a specialist calls `ask_owner` with nine questions
- **THEN** the call is refused to the model naming the limit and nothing is pending

### Requirement: A note that disagrees with the house file is resolved before numbers are proposed
When a text note attached by the owner gives a figure that disagrees with the house file or with a plan read in the same conversation, Intake SHALL list each disagreement in a table — what it is, the note's value, the other value and its source — and ask which value holds before proposing numbers through `record_brief` or `record_plan`. A disagreement SHALL never be resolved silently in either direction.

#### Scenario: Ceiling disagrees
- **WHEN** the house file has Wohnen's ceiling at 2500 mm and the attached note says 2450 mm
- **THEN** Intake's reply shows a table row for the ceiling with both values and their sources and asks which holds, and no brief is proposed in that turn

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

### Requirement: Questions about what the owner sees go to the Reviewer
A message asking whether something the owner sees in the Piece Inspector (a view such as front or exploded, a module or a part) is right, or asking for the piece to be checked against the brief, SHALL be handled by the Reviewer, within the existing rule that the Reviewer needs a screenshot or a render on the bound piece's latest version. A message asking to change what the owner sees SHALL stay with the Designer. The Foreman's instruction SHALL state this in one short line for the Reviewer and one rule, with no code-like detail.

#### Scenario: Question about a view
- **WHEN** the bound piece's latest version has a draft turntable and the owner writes "is the top shelf in the side view right?"
- **THEN** the Reviewer answers

#### Scenario: Question about the exploded view
- **WHEN** the bound piece's latest version has a draft turntable and the owner writes "is the shelf right in the exploded view?"
- **THEN** the Reviewer answers

#### Scenario: Change to what the owner sees
- **WHEN** the bound piece's latest version has a draft turntable and the owner writes "lower the top shelf in the side view"
- **THEN** the Designer answers

#### Scenario: Question with nothing rendered
- **WHEN** the bound piece's latest version has no screenshot or render and the owner asks whether the front view is right
- **THEN** the Reviewer is not chosen and the reply says what must exist first
