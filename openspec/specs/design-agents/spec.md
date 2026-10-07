# design-agents Specification

## Purpose
Defines the Foreman and its three specialists for the design loop: how a turn is routed, what Intake, the Designer and the Builder may do, which actions wait for the owner, how a spec the schema cannot express is refused and recorded, and how every render goes through the guard.

## Requirements

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

### Requirement: Intake turns a wish into confirmed numbers
Intake SHALL collect the brief — the room (by name, or its measurements), the piece's purpose and place, heights, style and budget — ask for what is missing without inventing a figure, and propose the confirmed numbers through `record_brief`, which pauses for the owner's `yes`. On `yes` the room, preferences and the brief are written to the house file; on `no` nothing is written and the reason returns to Intake.

#### Scenario: Numbers confirmed
- **WHEN** the owner confirms a hall 1200 mm wide and 2400 mm high with a 400 EUR budget
- **THEN** the house file holds the room and `budget_eur`, and the reply offers to design the piece

#### Scenario: Missing height
- **WHEN** the owner has not said how high the piece may be
- **THEN** Intake asks for the height and proposes no numbers

### Requirement: The Designer creates a piece from a validated spec
The Designer SHALL emit a complete custom-build document, starting from a shipped template and changing only what the brief supports, and call `create_piece` with it and a package id. The document SHALL be validated against the schema before anything else; a valid one is previewed (name, overall size in mm, module count, cut-list rows, hardware lines) and pauses for `yes`. On `yes` the piece and version 1 are recorded and the build starts; on `no` nothing is created and the reason returns to the Designer. A package id already in use SHALL be refused.

#### Scenario: Create confirmed
- **WHEN** the owner answers `yes` to a previewed hall bench
- **THEN** `hall-bench/v1` exists with the input document, the piece is recorded, and the build is queued

#### Scenario: Invalid document skips the pause
- **WHEN** the Designer's document fails validation
- **THEN** no confirmation is raised and the refusal naming the field returns to the Designer

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
`cut_list` SHALL return a version's derived parts (id, qty, length, width, thickness, material) and hardware lines from its stored document, with totals, without starting any Blender process.

#### Scenario: Parts listed
- **WHEN** the Designer calls `cut_list` for `hall-bench` version 1
- **THEN** the result lists every derived part with its dimensions and no process is started

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

### Requirement: The Builder builds and renders only through the guard
`blender_build` SHALL build a version that has not succeeded yet, wait for it within the Blender timeout, and report the outcome with the screenshot route; a version already built SHALL be reported as such without rebuilding. `render_turntable` SHALL require a tier, SHALL refuse raw frame, resolution or engine values by name, SHALL render a still or a turntable of a version alone or placed with a `room_fit` placement, and SHALL start the run and report the estimate for `draft` and `preview`; for `final` it SHALL pause with the estimate and run only on `yes`. The Builder SHALL never write or run Blender Python.

#### Scenario: Draft turntable
- **WHEN** the owner asks for a draft turntable of a built piece
- **THEN** the run is started at tier `draft` and the reply gives the estimate in plain terms and where the viewer will be

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
