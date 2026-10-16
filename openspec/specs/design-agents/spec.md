# design-agents Specification

## Purpose
Defines the Foreman and its three specialists for the design loop: how a turn is routed, what Intake, the Designer and the Builder may do, which actions wait for the owner, how a spec the schema cannot express is refused and recorded, and how every render goes through the guard.

## Requirements

### Requirement: The Foreman routes each turn to one specialist
Each turn SHALL be handled by exactly one specialist (Intake, Designer, Builder, Researcher, Reviewer or Lighting & materials), chosen by the Foreman from the conversation and the house file, or answered by the Foreman with one of its fixed questions below. Application rules bound the choice, in this order:
- A question the Researcher answers (a price, a product, a guideline) goes to the Researcher, with or without a confirmed room.
- A help question (how to use the app: its pages, conversations, rooms, renders, files or the design file template, and not a request to design, build, render, review or price something) goes to Intake, with or without a confirmed room, and before the room question below. A turn that carries a plan, a photo or a design file is never a help question. A help question does not change the conversation's confirmed room or bound piece.
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

#### Scenario: Help question in a new thread
- **WHEN** a conversation has no confirmed room and the owner writes "How do I use the design template?"
- **THEN** Intake answers, and the reply is not "Which room is this for?"

#### Scenario: Help question in a bound thread
- **WHEN** a conversation is about `hall-bench` and the owner asks "What is the difference between a draft and a final render?"
- **THEN** Intake answers, and the conversation stays bound to `hall-bench`

#### Scenario: Design file is not a help question
- **WHEN** a conversation has no confirmed room and the owner attaches a design file asking "how does this work?"
- **THEN** the reply is "Which room is this for?" and no specialist runs

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

### Requirement: A spec the schema cannot express is refused and recorded
When the Designer's document names a field the schema does not define, `create_piece` or `revise_package` SHALL refuse naming the field, SHALL record a generator-extension request with the field and the owner's words, and the Designer SHALL tell the owner plainly that the change is not expressible yet and has been recorded — never offering to write Blender code instead.

#### Scenario: Bevelled edge
- **WHEN** the owner asks for a bevelled front edge and the document carries `bevel_mm`
- **THEN** the reply says the bevel cannot be expressed yet and was recorded, a request naming `bevel_mm` exists, and no version was created

### Requirement: The Designer revises a piece from stated changes
`revise_package` SHALL take the piece's package id and a bounded set of changes — the name, the envelope, a material slot, per module (by its id) any field, modules to add or remove, extra parts to add or remove, per extra part (by its id) its placements and end cuts, part overrides — apply them to a copy of the latest version's document, refuse naming an unknown module or part id, validate the result, preview the change lines and pause for `yes`. On `yes` the next version is recorded as revised from the latest and built; the earlier version's folder and record are untouched. Only the round's first revision call is offered; a second in the same round is answered as not created.

A requested field whose value equals the latest version's value SHALL be dropped and SHALL give no change line. When every requested change is dropped this way, the revision SHALL be refused with a message saying nothing would change. No confirmation is raised and no version is created.

A change line for a module's `fronts` or `hardware` SHALL describe the list before and after the change, not only its length. A front is named by its type, count, opening or hinged side, height when set, and hinge item when it is not the default. A hardware line is named by its id, item and quantity.

A change to an extra part's placements SHALL place, move or unplace that part; an empty list unplaces it, so it is laid beside the build again. A change to its end cuts SHALL set or clear them. The change line SHALL describe the placements before and after, or "beside the build" when unplaced. Each piece is described by its corner position in mm, its orientation, and its roll and tilt when set. Changed end cuts are described before and after, or "square" when none. The number of placements SHALL equal the part's quantity, or the change is refused naming the part.

#### Scenario: Shelves changed
- **WHEN** the owner says "three shelves in the cabinet" and confirms
- **THEN** version 2 exists with "cabinet: shelves 2 → 3" and version 1 is unchanged

#### Scenario: Unknown module
- **WHEN** the change names module `drawers` which the piece does not have
- **THEN** it is refused naming `drawers` and listing the piece's modules, and no confirmation is raised

#### Scenario: Fronts change shown in full
- **WHEN** module `cabinet` has two hinged doors and the change replaces them with one hinged door and one 200 mm drawer
- **THEN** the confirmation lists "cabinet: fronts" with "2 doors (hinge)" before and "1 door (hinge), 1 drawer 200 mm" after, and no line reads "entries"

#### Scenario: Hardware change shown in full
- **WHEN** a module's hardware line `handle` changes quantity from 2 to 4
- **THEN** the change line names `handle`, its item, "×2" before and "×4" after

#### Scenario: No-op field dropped
- **WHEN** the change sets `cabinet` height to its current 2238 and shelves from 6 to 3
- **THEN** the confirmation lists only "cabinet: shelves 6 → 3"

#### Scenario: Revision that changes nothing
- **WHEN** every requested field equals the latest version's value
- **THEN** the tool refuses saying nothing would change, no confirmation is raised, and no version is created

#### Scenario: Extra part placed
- **WHEN** extra part `top-frame` (qty 1, 1200 × 60 mm) is laid beside the build and the change places it at x 0, y 0, z 900 with length along x and width along y, and the owner confirms
- **THEN** the confirmation lists "top-frame: placements beside the build → x0 y0 z900, length along x, width along y", and the next version draws `top-frame` at that position

#### Scenario: Placement count disagrees with quantity
- **WHEN** extra part `slat` has qty 4 and the change gives 3 placements
- **THEN** it is refused naming `slat` and saying 4 placements are needed, and no confirmation is raised

#### Scenario: Brace tilted and cut
- **WHEN** the change places extra part `brace` at x 100 y 0 z 0, length along x, width along y, with tilt 30° towards z, and sets its end cuts across width to 30° and −30°
- **THEN** the confirmation lists the placement with "tilt 30° towards z" and "brace: end cuts square → 30° / −30° across width"

#### Scenario: Unknown extra part
- **WHEN** the change places extra part `rail` which the piece does not have
- **THEN** it is refused naming `rail` and listing the piece's extra parts, and no confirmation is raised

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
`blender_build` SHALL build a version that has not succeeded yet, wait for it within the Blender timeout, and report the outcome with the screenshot route; a version already built SHALL be reported as such without rebuilding. `render_turntable` SHALL require a tier, `draft` or `final`, and SHALL refuse raw frame, resolution or engine values by name. It SHALL render a still or a turntable of a version alone or placed with a `room_fit` placement, except that a `draft` of a piece version alone SHALL be a turntable: a `draft` still of a piece version alone SHALL be refused, saying a draft of a piece is a turntable. For `draft` it SHALL start the run and report the estimate; for `final` it SHALL pause with the estimate and run only on `yes`. When a render starts, the reply SHALL give the estimate and SHALL NOT give a viewer route: for a piece version it SHALL say that a Review button appears in this chat when the render finishes, and for a shell or composition that a notice appears in this chat. The Builder SHALL never write or run Blender Python.

#### Scenario: Draft turntable
- **WHEN** the owner asks for a draft turntable of a built piece
- **THEN** the run is started at tier `draft` and the reply gives the estimate in plain terms and says a Review button appears in this chat when it finishes, with no viewer route

#### Scenario: Draft still of a piece refused
- **WHEN** the Builder's call asks for a `draft` still of a built piece on its own
- **THEN** it is refused saying a draft of a piece is a turntable, and no process starts

#### Scenario: Draft still of a placed piece
- **WHEN** the Builder's call asks for a `draft` still of a built piece placed with a `room_fit` placement
- **THEN** the run is started at tier `draft` and the reply gives the estimate

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

### Requirement: The Designer confirms the change list before revising
Before calling `revise_package`, the Designer SHALL restate the changes it understood as a list and ask the owner whether anything else should change. It SHALL call `revise_package` only after the owner says the list is complete. That one call SHALL carry every change asked for since the last created revision. When the owner answers with a further change, the Designer SHALL add it to the list and ask again. When the owner declines a revision with a reason, the Designer SHALL treat the reason as one more change, restate the whole list and ask again, and SHALL NOT call `revise_package` again in that reply.

#### Scenario: Change restated first
- **WHEN** the owner asks "make the cabinet 600 wide"
- **THEN** the Designer's reply restates "cabinet: width → 600 mm", asks whether anything else should change, and no confirmation is raised

#### Scenario: Changes gathered into one call
- **WHEN** the owner then adds "and three shelves", and then says that is all
- **THEN** one `revise_package` call carries both the width and the shelves, and one confirmation lists both

#### Scenario: Decline reason becomes a change
- **WHEN** the owner answers the confirmation with no and the reason "keep two shelves"
- **THEN** no version is created, and the Designer's reply restates the list with the shelves change corrected and asks again without raising a new confirmation in that reply

### Requirement: The Designer confirms the change list before recomposing
When the owner asks to change a room or apartment that already has a composition version, the Designer SHALL first restate the changes it understood as a list, one line per item added, moved or removed, naming each item by its id. It SHALL then ask the owner whether anything else should change. It SHALL call `compose_room` only after the owner says the list is complete. That one call SHALL carry every change asked for since the composition's latest version. When the owner answers with a further change, the Designer SHALL add it to the list and ask again. When the owner declines the `compose_room` summary with a reason, the Designer SHALL treat the reason as one more change, restate the whole list and ask again, and SHALL NOT call `compose_room` again in that reply. A first composition of a room or apartment SHALL NOT need this step.

#### Scenario: Removal restated first
- **WHEN** `Wohnen` v7 holds `corner-couch` and the owner writes "remove the corner couch please"
- **THEN** the Designer's reply restates "corner-couch: remove", asks whether anything else should change, no confirmation is raised and no version is created

#### Scenario: Changes gathered into one call
- **WHEN** the owner then adds "and move the dining table 300 mm towards wall 1", and then says that is all
- **THEN** one `compose_room` call carries both the removal and the move, and one summary lists `corner-couch` as removed and `dining-table` as moved

#### Scenario: Decline reason becomes a change
- **WHEN** the owner answers the summary with no and the reason "keep the couch, just move it 200 mm along wall 5"
- **THEN** no version is created, and the Designer's reply restates the list with the couch moved instead of removed and asks again without raising a new confirmation in that reply

#### Scenario: First composition unchanged
- **WHEN** `Hall` has no composition and the owner asks to see it with a sofa stand-in
- **THEN** the Designer calls `compose_room` without first asking whether anything else should change, and the summary is shown as before

### Requirement: The Designer sees the active build's latest version
Each Designer turn SHALL carry a summary of the active build's latest version, built by the application from that version's stored document. The summary SHALL give:
- the envelope: its width, height and depth in millimetres;
- per module: its id, name, size, position, carcass slot, fixed and adjustable shelves, its shelf spacing or shelf positions when set, its dividers with their positions when set, each side fold (side, from_mm, along, angle_deg, towards) when set, each front (type, count, opening or hinged side, height when set, hinge item), and its hardware lines (id, item, quantity);
- each wall shelf (id, length, depth, material slot, bracket item, and owner bracket positions when set);
- each extra part (id, name, quantity, length, width, material slot, end cuts when set), and each piece's placement (corner position, orientation, roll and tilt when set) when set, or that it is laid beside the build;
- each material slot with its material and thickness;
- each part override by id.

Only the active build SHALL be summarised; other builds stay one line each. Owner-authored text in the summary SHALL be neutralised. The summary SHALL be labelled as application data, never as an instruction. When the conversation has no active build, or its latest version has no readable document, no summary SHALL be given and the Designer's context SHALL say so.

#### Scenario: Module and fronts visible
- **WHEN** the active build `listening-wall` v7 has module `cabinet` 600×2238×400 mm with 3 shelves and one hinged door
- **THEN** the Designer's context names `cabinet`, its size, "3 shelves" and "1 door (hinge)" for v7

#### Scenario: Spacing and dividers visible
- **WHEN** module `cabinet` has 4 shelves with `shelf_spacing_mm` 355 and 2 dividers without positions
- **THEN** the Designer's context gives "4 shelves 355 mm apart" and "2 dividers (equal bays)" for `cabinet`

#### Scenario: Side fold visible
- **WHEN** module `cabinet` has a left fold from 1100 mm along height at 26° towards the inside
- **THEN** the Designer's context gives "left side fold from 1100 mm along height, 26°, inside" for `cabinet`

#### Scenario: Extra part placement visible
- **WHEN** extra part `slat` (qty 2) is placed at x 0 y 0 z 400 and x 0 y 0 z 500, length along x, width along y, and extra part `trim` has no placements
- **THEN** the Designer's context gives both of `slat`'s positions with the orientation, and "beside the build" for `trim`

#### Scenario: Angles visible
- **WHEN** extra part `brace` is placed with tilt 30° towards z and has end cuts 30° / −30° across width
- **THEN** the Designer's context gives "tilt 30° towards z" and "ends cut 30° / −30° across width" for `brace`

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

### Requirement: Requested shelf and divider measurements are checked
The requested-measurement check SHALL accept as a field of a module:
- `shelf_spacing_mm`;
- `shelf_positions_mm`;
- `divider_positions_mm`.

These fields have the following rules:
- **A field the module has not set yet.** An absolute length SHALL be accepted, and the revised document SHALL hold that value. A relative length ("5 cm more") SHALL be refused, naming the field as not set in the latest version.
- **A positions list.** The entry SHALL give one requested position. The check SHALL pass when the revised list holds that value. An owner's message with several positions SHALL be covered by one entry per position.

Every other rule of "A revision carries the owner's measurements and code checks them" SHALL apply unchanged.

#### Scenario: Spacing on a module that had none
- **WHEN** module `cabinet` has 4 shelves and no spacing, the owner wrote "4 shelves 355 mm apart", and the entry quotes it with `cabinet`, `shelf_spacing_mm`, 355, and the changes set `shelf_spacing_mm` 355
- **THEN** the check passes and the confirmation is raised with "cabinet: shelf_spacing_mm not set → 355"

#### Scenario: Invented spacing refused
- **WHEN** the owner wrote "355 mm apart" and the changes set `shelf_spacing_mm` 373
- **THEN** the call is refused naming "355 mm apart", 355 expected and 373 set

#### Scenario: Divider position covered
- **WHEN** the owner wrote "a divider 400 mm from the left", and the entry quotes it with `cabinet`, `divider_positions_mm`, 400, and the changes set `divider_positions_mm` [400]
- **THEN** the check passes

### Requirement: A revision past the version limit is refused by code
When a piece already holds 15 versions, `revise_package`, and the rebuild of an unchanged piece, SHALL refuse before asking for confirmation. The refusal SHALL be written by code and SHALL say that the piece has 15 versions and that the owner can delete one on the Pieces page or in the Project panel and then ask again. The Designer SHALL relay that refusal and SHALL NOT propose deleting a version itself. When the new version would be the 13th, 14th or 15th the piece holds, the confirmation summary SHALL add a line written by code: "This will be version <n> of 15 the piece can hold."

#### Scenario: Revision refused at the limit
- **WHEN** `listening-wall` holds 15 versions and the owner asks "make the shelves 20 mm thicker"
- **THEN** no confirmation is shown, no version is made, and the reply says the piece has 15 versions and one can be deleted on the Pieces page or in the Project panel

#### Scenario: Heads-up near the limit
- **WHEN** `listening-wall` holds 12 versions and the Designer proposes a revision
- **THEN** the confirmation summary includes "This will be version 13 of 15 the piece can hold."

#### Scenario: No heads-up early
- **WHEN** `listening-wall` holds 4 versions and the Designer proposes a revision
- **THEN** the confirmation summary has no version-limit line

### Requirement: Requested side-fold measurements are checked
The requested-measurement check SHALL accept `side_folds` as a field of a module. The entry SHALL give one requested `from_mm`. The check SHALL pass when the revised list holds a fold with that `from_mm`. An owner's message with several such lengths SHALL be covered by one entry per length.

A module that has no folds yet SHALL accept an absolute length, and the revised document SHALL hold that value. A relative length ("5 cm more") SHALL be refused, naming the field as not set in the latest version.

An angle in degrees SHALL NOT be treated as a length. Every other rule of "A revision carries the owner's measurements and code checks them" SHALL apply unchanged.

#### Scenario: Bend datum on a module that had no fold
- **WHEN** module `cabinet` has no folds, the owner wrote "The left side of the carcass should have a 26 degree bend from 1100 mm", the entry quotes "1100 mm" with `cabinet`, `side_folds`, 1100, and the changes set a left fold with `from_mm` 1100
- **THEN** the check passes and the confirmation is raised

#### Scenario: Invented datum refused
- **WHEN** the owner wrote "from 1100 mm" and the changes set `from_mm` 1000
- **THEN** the call is refused naming "1100 mm", 1100 expected and 1000 set

#### Scenario: Relative fold datum refused when unset
- **WHEN** module `cabinet` has no folds, the owner wrote "5 cm higher", and the entry uses `side_folds` as a relative change
- **THEN** the call is refused naming `side_folds` as not set in the latest version

### Requirement: The Designer may put fronts on a folded carcass
The Designer's instructions SHALL say that a module with `side_folds` may carry overlay fronts, adjustable shelves and dividers, that those fronts follow the folded opening (an n-gon when the outline is not a rectangle), and that dividers on a fold without positions split the narrowest opening along their span into equal bays. Bevels SHALL stay unexpressible.

#### Scenario: Instructions allow fronts on a fold
- **WHEN** the Designer's instructions are loaded
- **THEN** they name `side_folds` together with fronts, adjustable shelves and dividers, and they no longer say dividers on a fold are not expressible

#### Scenario: A panel bend is side_folds
- **WHEN** the Designer's instructions are loaded
- **THEN** they say a bend in a carcass side is the field `side_folds`, that the Designer must never tell the owner there is no field for a bend angle, and that the field applies to the module the owner named (its id from the piece summary)

### Requirement: The Designer can express a partial-height divider
The Designer's instructions SHALL say that a divider that does not run the full height is expressed with `divider_spans`, one entry per divider, left to right, each with `from_board` (`"bottom"` or a shelf number counting every shelf from the lowest) and `to_board` (`"top"` or a shelf number), and that only fixed shelves can anchor a divider. They SHALL give "a vertical wall from the top shelf to the top of the cabinet" on a module with 4 fixed shelves as `"dividers": 1, "divider_spans": [{"from_board": 4, "to_board": "top"}]`. The Designer SHALL restate the span in the change list and wait until the owner says the list is complete. The Designer SHALL never tell the owner that a partial-height divider cannot be made.

The piece summary SHALL name each divider's span when spans are set, e.g. "1 divider (equal bays) from shelf 4 to the top", and each shelf's kind when `shelf_kinds` is set, e.g. "shelf kinds (lowest first): adjustable, adjustable, adjustable, fixed".

#### Scenario: Instructions name divider spans
- **WHEN** the Designer's instructions are loaded
- **THEN** they name `divider_spans`, `from_board` and `to_board`, and give the top-shelf-to-top example

#### Scenario: Span visible in the summary
- **WHEN** module `cabinet` has 1 divider with `divider_spans` [{`from_board`: 4, `to_board`: "top"}]
- **THEN** the Designer's context gives "1 divider (equal bays) from shelf 4 to the top" for `cabinet`

#### Scenario: Full-height summary unchanged
- **WHEN** a module has 2 dividers without spans
- **THEN** the Designer's context gives "2 dividers (equal bays)" as before

#### Scenario: Shelf kinds visible in the summary
- **WHEN** module `cabinet` has `shelf_kinds` ["adjustable", "adjustable", "adjustable", "fixed"]
- **THEN** the Designer's context gives "shelf kinds (lowest first): adjustable, adjustable, adjustable, fixed" for `cabinet`

### Requirement: The Designer asks where a new divider goes
When `create_piece` or `revise_package` is called with a new divider (the count rises, or a span is added) and the revised module has no `divider_positions_mm`, the tool SHALL NOT propose the version. It SHALL instead return, computed by code:
- the centred position for each divider (equal compartments; on a folded module, of the narrowest opening along its span), in millimetres from the left side's inner face;
- the compartment widths at each shelf the divider splits, or across its span when it splits none;
- for each compartment, the configured shelf-span limit for the board's thickness with its cited source and whether the compartment is within it; or the statement that no shelf-span limit is configured.

The Designer SHALL relay this to the owner (through the Foreman) as a question: the recommended position, the compartment widths, the limit or its absence, and any guideline passages `search_guidelines` returns on shelf spans or dividers, each cited. The Designer SHALL then write the position the owner accepts or gives as `divider_positions_mm`. A design imported from a file SHALL NOT be refused for missing positions.

#### Scenario: Position asked with no limit configured
- **WHEN** the owner asks for "a vertical wall from the top shelf to the top of the cabinet" on the 800 mm `cabinet` with 4 fixed shelves and no position, and no shelf-span rule is configured
- **THEN** no version is proposed, and the owner is asked to confirm a divider 373 mm from the left side's inner face, giving two 373 mm compartments, with the statement that no shelf-span limit is configured yet

#### Scenario: Position asked with a limit configured
- **WHEN** a shelf-span rule gives 800 mm for 18 mm boards with its cited source, and the owner asks for one divider without a position across shelves 1164 mm wide
- **THEN** the recommendation gives two 573 mm compartments, says both are within 800 mm, and cites the rule's source

#### Scenario: Owner gives the position
- **WHEN** the owner answers "200 mm from the left"
- **THEN** the revision carries `divider_positions_mm` [200], and the measurement check holds it against the owner's words

#### Scenario: Import not asked
- **WHEN** an imported design has dividers without positions
- **THEN** it is accepted with equal bays, as before

### Requirement: The Designer asks before fixing a shelf
When the owner asks for a divider that would stand on or reach an adjustable shelf, the Designer SHALL tell the owner (through the Foreman) that only a fixed shelf can hold a divider, name the shelf, and ask whether to fix it. The question SHALL state what changes: that shelf becomes a fixed board screwed with 4 confirmat screws, and the module needs that shelf's pins fewer. When the owner agrees, the Designer SHALL revise `shelves`, `adjustable_shelves` and `shelf_kinds` together with the divider in one revision, whose preview lists the hardware and cut-list changes. When the owner declines, the Designer SHALL not add the divider and SHALL say so. The Designer SHALL never change a shelf's kind without the owner's yes.

#### Scenario: Owner agrees to fix the top shelf
- **WHEN** `cabinet` has 4 adjustable shelves and the owner asks for a divider from the top shelf to the top, then answers yes to fixing shelf 4
- **THEN** the proposed revision sets `shelves` 1, `adjustable_shelves` 3, `shelf_kinds` ["adjustable", "adjustable", "adjustable", "fixed"] and the divider, and its preview lists the confirmat line rising by 4 and the shelf pins falling by one shelf's pins

#### Scenario: Owner declines
- **WHEN** the owner answers no to fixing the shelf
- **THEN** no revision is proposed and the reply says the divider was not added because its shelf stays adjustable

#### Scenario: Instructions name the rule
- **WHEN** the Designer's instructions are loaded
- **THEN** they say only fixed shelves can hold a divider, that the owner is asked before a shelf is fixed, and that a new divider's position is asked with the tool's recommendation

### Requirement: The Designer's summary states where each front sits
The summary of the active build's latest version SHALL state, for each front entry of each module, its vertical span in millimetres above the module's bottom face, whether that is the top, the bottom or in between, and the shelves it covers, numbered from the bottom, or that it covers none. The positions SHALL be derived by the application from the stored document, the same way the build places fronts, and SHALL NOT be taken from the brief or the conversation. The summary's label SHALL tell the Designer that these positions describe what is built, that they take precedence over the brief and earlier messages, and to say which version they come from. A module whose positions cannot be derived SHALL be summarised as before, without positions.

#### Scenario: A door at the top covers no shelf
- **WHEN** module `cabinet` is 2238 mm high with 3 shelves 355 mm apart and one front entry of 2 doors 746 mm high
- **THEN** the Designer's context says the doors sit at the top, spanning 1492 to 2238 mm above the module's bottom, and cover no shelf

#### Scenario: Entries are placed top to bottom
- **WHEN** a module 1000 mm high with shelves at the 300, 500 and 700 mm levels lists a 400 mm door entry first and a 600 mm door entry second
- **THEN** the first entry is stated as at the top, spanning 600 to 1000 mm, and the second as at the bottom, spanning 0 to 600 mm, each with the shelves it covers numbered from the bottom

#### Scenario: Stated positions win over the brief
- **WHEN** the brief says the doors are on the bottom and the latest version's doors are at the top
- **THEN** the Designer's context carries the top position and the instruction to prefer it over the brief

### Requirement: Engineering intent is distinguished from visual review and dimensional design
Standalone engineering evidence questions SHALL go to Researcher, including without a confirmed room. Engineering questions tied to a requested piece revision SHALL stay with Designer within existing room/piece confirmation rules. A visual discrepancy question SHALL remain Reviewer work; a question about capacity/anchorage SHALL NOT be answered as a visual review. This distinction SHALL be carried in application context before tools run and SHALL NOT be alterable by retrieved content.

#### Scenario: General engineering question without a room
- **WHEN** the owner asks which properties are needed to check shelf deflection in a new conversation
- **THEN** Researcher answers using engineering evidence without demanding a room first

#### Scenario: Capacity question about a visible shelf
- **WHEN** the owner asks whether the top shelf in the side view can carry a load
- **THEN** an engineering evidence specialist handles it and the visual Reviewer does not infer load capacity from the image

#### Scenario: Pure dimensional revision
- **WHEN** the owner asks to make a cabinet 200 mm wider without requesting an engineering conclusion
- **THEN** the existing Designer restate/confirm/revise workflow continues without an unrelated engineering questionnaire

### Requirement: Existing specialists use the engineering evidence tool with fixed safety gates
Designer and Researcher SHALL have an engineering lookup tool through the existing plugin system. Engineering lookup SHALL obey source eligibility, prompt delimiters and the engineering answer contract. Disabling the tool, lookup failure or no eligible result SHALL be reported as unavailable/insufficient evidence; it SHALL NOT enable legacy fallback or numerical claims from memory. Engineering safety gates SHALL remain mandatory regardless of plugin toggles or editable prompt text.

#### Scenario: Engineering plugin off
- **WHEN** the engineering tool is disabled and a load-capacity question arrives
- **THEN** the reply says lookup is unavailable and capacity is NOT VERIFIED, without a fallback claim

#### Scenario: Lookup fails
- **WHEN** the evidence store cannot be consulted
- **THEN** the owner sees the lookup limitation and no invented rule or load rating

### Requirement: Intake answers help questions from the help source
When the Foreman routes a help question to Intake, Intake SHALL answer it from the help source through `read_help`, in its own words and no longer than the question needs, and SHALL NOT state a step, page, button or limit that the help source does not hold. When the help source does not cover the question, Intake SHALL say so and point to the Help page. A help turn SHALL NOT record a brief, a room, a plan or a piece, and SHALL NOT raise a confirmation.

#### Scenario: Template question answered
- **WHEN** the owner asks "How do I turn a photo of a cabinet into a design?"
- **THEN** Intake reads the template topic and replies with its steps: download the template, give it with the photo and the default prompt to an AI chat that reads images, attach the returned `.json` file in a new conversation, confirm the import, then revise the piece

#### Scenario: Not covered
- **WHEN** the owner asks a help question no topic covers
- **THEN** the reply says the help does not cover it and points to the Help page, and no step is invented

#### Scenario: Nothing recorded
- **WHEN** Intake answers a help question in a conversation with no brief
- **THEN** the house file and the conversation's room and piece are unchanged
