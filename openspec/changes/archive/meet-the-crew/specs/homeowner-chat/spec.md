## MODIFIED Requirements

### Requirement: A thread's history shows every reply the owner was meant to read
Reading a thread SHALL return, in order, the owner's messages, every assistant message that has text (including one sent together with tool calls), one `confirmation` entry per answered confirmation, and one `notice` entry per render notice posted to the thread. Every assistant entry that shows reply text SHALL carry a `speaker`: the role key of the specialist that wrote it (`intake`, `designer`, `builder`, `lighting`, `reviewer` or `researcher`), `engineering` when it is an engineering answer (whichever specialist wrote it), or `foreman` when the application wrote it without a specialist (for example the room question, the fixed height reply or a refusal before a specialist ran). An assistant message saved before speakers were recorded SHALL carry `foreman`. The speaker SHALL be a role key only, never a model name or slug. A `confirmation` entry SHALL carry its subject, its plain title, its summary, the owner's answer (with the reason when one was given) and, when the confirmation had one, its table of calculations (column names and rows). The plain title SHALL be composed by the application from the subject, with no model call. Each subject SHALL have a fixed title in plain words (for example "Composing room" for a room change, "Revising piece" for a revision, "Importing design" for a design import), and an unknown subject SHALL be titled "Confirmation". No title, row or summary shown to the owner SHALL contain a tool's internal name. A notice SHALL come after every message the thread held when it was posted. A `notice` entry SHALL carry its text, its outcome (`succeeded` or `failed`) and the render's tier, and, for a render of a piece version, the piece's id and the version. Tool calls, tool arguments and tool results SHALL NOT appear. An assistant message with tool calls and no text SHALL NOT produce an entry. The entries SHALL obey the no-internals rule.

#### Scenario: Text sent with a tool call is shown
- **WHEN** the Designer replies "Here's how your spec forces the dimensions…" and calls `create_piece` in the same message
- **THEN** reading the thread returns that text as an assistant entry with the speaker `designer`, and no entry contains the tool's arguments

#### Scenario: Speaker of each reply
- **WHEN** a thread holds a reply from Intake, then the room question written by the application, then a reply from the Researcher
- **THEN** reading the thread returns the speakers `intake`, `foreman` and `researcher`, in that order

#### Scenario: Engineering answer
- **WHEN** the Researcher answers an engineering question about how much a shelf can hold
- **THEN** the reply's entry has the speaker `engineering`

#### Scenario: Reply saved before speakers
- **WHEN** a thread holds a reply saved before this change
- **THEN** its entry has the speaker `foreman`

#### Scenario: Answered confirmation stays visible
- **WHEN** the owner answers `no` with the reason "make it 4 shelves" to a pending revision
- **THEN** reading the thread returns a `confirmation` entry with the subject `revise`, the title "Revising piece", the summary the owner was shown and the answer `no` with that reason, before the reply that followed

#### Scenario: Room change keeps its calculations
- **WHEN** the owner answers `yes` to a room change in `Wohnen` that places a sofa and a lamp
- **THEN** the `confirmation` entry has the title "Composing room" and a table with one row for the sofa and one for the lamp

#### Scenario: Unknown subject
- **WHEN** an answered confirmation's subject has no title
- **THEN** its entry is titled "Confirmation" and the subject is not shown to the owner

#### Scenario: Confirmation answered before titles existed
- **WHEN** a thread holds a room change answered before this change
- **THEN** its entry has the title "Composing room", its summary and no table

#### Scenario: Pending confirmation is not yet an entry
- **WHEN** a confirmation is pending
- **THEN** reading the thread returns it as the pending confirmation and not as a history entry

#### Scenario: Notice after the reply that started the render
- **WHEN** the Builder's reply says a draft turntable of `hall-bench` version 1 has started, and that render then finishes
- **THEN** reading the thread returns the Builder's reply and after it a `notice` entry with outcome `succeeded`, tier `draft`, package `hall-bench` and version 1

## ADDED Requirements

### Requirement: Texts the application writes name the crew by persona
A text written by the application (not by a model) that the owner reads and that names an agent SHALL name it by its persona: the Foreman as "Little Homey", Intake as "Lil' Worm", the Designer as "Lil' Glitty", the Builder as "Muscles", Lighting & materials as "Bulbs", the Reviewer as "Mr. Lookback" and the Researcher as "Money Bags". This SHALL cover the token-budget refusal ("<persona> can't take this on right now: <reason>.") and the empty-answer reply. Agent instructions, the notes composed into prompts, and the developer pages SHALL keep the role names.

#### Scenario: Budget refusal
- **WHEN** the Designer's model has reached its daily ceiling and the owner sends a message routed to the Designer
- **THEN** the reply reads "Lil' Glitty can't take this on right now: today's limit is reached; it resets at midnight."

#### Scenario: Prompts keep role names
- **WHEN** the Designer answers a turn
- **THEN** its prompt still says it is the Designer, and contains no persona name
