# homeowner-chat Specification

## Purpose
Defines how the homeowner talks to the Foreman: conversations as threads, one turn at a time, a pending confirmation that pauses a turn until the owner answers, what the homeowner may see, and how a turn is traced and refused.

## Requirements

### Requirement: Threads are started, listed and read
The owner SHALL be able to start a conversation (optionally naming the piece it is about), list conversations, and read one conversation's messages and pending confirmation. A thread id SHALL be issued by the service, never chosen by the client, and every thread route SHALL require the owner's session.

#### Scenario: Start and read
- **WHEN** the owner starts a thread and sends one turn
- **THEN** reading the thread returns the owner's message, the reply and no pending confirmation

#### Scenario: Not signed in
- **WHEN** a thread route is called without the session cookie
- **THEN** the response is 401

### Requirement: A turn is one message in, one reply out
Sending a message to a thread SHALL run exactly one Foreman turn and answer with the reply text, which specialist answered (by role name only), and either nothing pending or a pending confirmation. The turn SHALL be bounded: after the configured number of tool rounds the specialist answers in text with no further tool calls, and every model call in it is fitted to its model's token budget before it is sent.

#### Scenario: Plain turn
- **WHEN** the owner writes "I want a bench for the hall"
- **THEN** the reply is text from Intake and nothing is pending

#### Scenario: Round cap
- **WHEN** a specialist would call tools more times than the cap allows
- **THEN** the turn ends with a text reply that says what remains undone

### Requirement: A thread carries its tool toggles
Each thread SHALL have a tool setting per toggleable plugin, starting from the manifest's default; the owner SHALL be able to read and change them on the thread through an owner-gated route, and a change SHALL apply from the thread's next turn. A pending confirmation SHALL resume with the tools of the turn that raised it.

#### Scenario: Toggles listed
- **WHEN** the owner reads a new thread's tools
- **THEN** each toggleable plugin is listed with its manifest default

### Requirement: A confirmation pauses the turn until the owner answers
When a gated action is proposed — confirmed numbers, a new piece, a revision, a `final` render — the turn SHALL pause and the reply SHALL carry a pending confirmation with a stable id, a subject, a readable summary and the structured proposal. The owner answers it on the thread with `yes` or `no` and an optional reason; `yes` runs the action and `no` returns the reason to the specialist, which continues the conversation. An answer naming no pending confirmation, or a stale id, SHALL be refused with 409. A new message while a confirmation is pending SHALL be refused with 409 naming the pending subject.

#### Scenario: Revision confirmed
- **WHEN** the Designer proposes "cabinet: 2 shelves → 3" and the owner answers `yes`
- **THEN** the revision is created and the reply reports the new version

#### Scenario: Declined with a reason
- **WHEN** the owner answers `no` with "make it 4 shelves"
- **THEN** nothing is created and the next reply proposes a changed revision

#### Scenario: Stale answer
- **WHEN** the owner answers a confirmation id that is no longer pending
- **THEN** the response is 409 and nothing runs

### Requirement: The homeowner sees no internals
No chat response SHALL contain a model name or slug, a prompt, a token count, a cost, a tool's internal arguments or a file-system path. A tool's result reaches the owner as the specialist's words and, where a file was produced, as the package route that serves it.

#### Scenario: Build reported
- **WHEN** the Builder finishes a build
- **THEN** the reply names the package and version and points at the screenshot route, and the response body contains no model slug, token figure or host path

### Requirement: Memory failure is a stated refusal
When the checkpointer is unavailable the turn SHALL be refused with a 503 whose body states that the conversation memory is not available; nothing SHALL run and the owner's message SHALL not be stored half-way. A gateway failure on the model call SHALL be reported as a stated inability with its class and SHALL leave the unanswered message out of the thread.

#### Scenario: Checkpointer down
- **WHEN** the service started without a checkpointer and the owner sends a turn
- **THEN** the response is 503 with the memory reason

#### Scenario: Gateway timeout
- **WHEN** the specialist's model call times out
- **THEN** the response reports failure class `timeout` and the thread does not hold the unanswered message

### Requirement: Turns are traced and metered
Each turn SHALL run under the tracing callback (when configured) with the owner id as user, the thread id as session and the bound piece as project, and SHALL record one usage row per model call naming the slot's model and the trace id. Tracing being off or failing SHALL not change the turn.

#### Scenario: Usage per slot
- **WHEN** a turn routes through the Foreman to the Designer
- **THEN** usage rows exist for both calls, each naming its slot's model

### Requirement: A thread's history shows every reply the owner was meant to read
Reading a thread SHALL return, in order, the owner's messages, every assistant message that has text (including one sent together with tool calls), and one `confirmation` entry per answered confirmation carrying its subject, its summary and the owner's answer (with the reason when one was given). Tool calls, tool arguments and tool results SHALL NOT appear. An assistant message with tool calls and no text SHALL NOT produce an entry. The entries SHALL obey the no-internals rule.

#### Scenario: Text sent with a tool call is shown
- **WHEN** the Designer replies "Here's how your spec forces the dimensions…" and calls `create_piece` in the same message
- **THEN** reading the thread returns that text as an assistant entry, and no entry contains the tool's arguments

#### Scenario: Answered confirmation stays visible
- **WHEN** the owner answers `no` with the reason "make it 4 shelves" to a pending revision
- **THEN** reading the thread returns a `confirmation` entry with the subject `revise`, the summary the owner was shown and the answer `no` with that reason, before the reply that followed

#### Scenario: Pending confirmation is not yet an entry
- **WHEN** a confirmation is pending
- **THEN** reading the thread returns it as the pending confirmation and not as a history entry

### Requirement: A thread reports its piece's progress
The owner SHALL be able to read, on a thread, where the piece it is about stands: whether a brief is confirmed, whether a piece exists and its latest version with that version's build state, whether that version has a screenshot, a draft or preview render, a review (with the count of open items), a detail pass, and a final render, and which of these is the next step the owner can ask for. The read SHALL also list the piece's open generator-extension requests by field and the owner's words. A thread with no bound piece SHALL report only the brief state and the next step. The read SHALL be derived from the house file, the version folder and the thread's own conversation state, and SHALL contain no model name, prompt, token count, cost or file-system path; an image is named by its package route, and so is the latest version's turntable viewer when its turntable is published.

#### Scenario: Fresh thread
- **WHEN** the owner reads the progress of a thread that has had no turn
- **THEN** no piece is reported, the brief is not confirmed, and the next step is to describe the piece

#### Scenario: Built and reviewed
- **WHEN** the thread's piece has version 2 built with a draft turntable and a review with two open items
- **THEN** the progress shows version 2 built, a draft rendered, the review with 2 open items, no detail pass, no final, and names the screenshot by its package route

#### Scenario: Extension request on the piece
- **WHEN** the Designer has recorded a request naming `bevel_mm` for the thread's piece
- **THEN** the progress lists `bevel_mm` with the owner's words among the open requests

#### Scenario: No internals
- **WHEN** the owner reads the progress of any thread
- **THEN** the body contains no model slug, no token figure and no host path

### Requirement: A turn binds the thread to the piece it creates or revises
When a confirmed action creates a piece or revises one, the thread SHALL be bound to that piece, replacing any earlier binding, so the thread's list entry and later turns name the piece last worked on. A declined or failed action SHALL bind nothing.

#### Scenario: Created in the conversation
- **WHEN** the owner confirms a new piece `hall-bench` on a thread started without a piece
- **THEN** reading the thread shows it is about `hall-bench`, and the thread list shows the same

#### Scenario: Revised on an unbound thread
- **WHEN** the owner confirms a revision of `hall-bench` on a thread with no piece
- **THEN** the thread is about `hall-bench`

#### Scenario: A second piece
- **WHEN** a thread about `hall-bench` has a confirmed new piece `shelf`
- **THEN** the thread is about `shelf` from then on

#### Scenario: Declined
- **WHEN** the owner answers `no` to a new piece
- **THEN** the thread's piece is unchanged

#### Scenario: Turntable published
- **WHEN** the latest version's draft turntable has finished
- **THEN** the progress names its viewer by its package route; before it finishes the viewer is null

### Requirement: A conversation can be deleted
The owner SHALL be able to delete a conversation through an owner-gated route. A delete removes, in this order:
1. the conversation's memory in the checkpointer; if that fails, the delete is refused with the memory refusal and nothing else is touched;
2. its index entry, together with its tool settings and upload records;
3. its upload files.

Pieces, versions, renders, rooms, preferences, reviews, render feedback and recorded usage SHALL be unchanged. A delete SHALL be refused with 409, saying a reply is still being written, while a turn or a resume is running on that thread. An unknown thread id SHALL answer 404. A deleted conversation cannot be restored.

#### Scenario: Delete a conversation with a piece
- **WHEN** the owner deletes a thread that created `murphy-bed` versions 1 and 2 and holds two uploads
- **THEN** the thread is gone from the list, reading it answers 404, its uploads answer 404 and their files are gone, and `murphy-bed` with both versions and their renders is still on the Pieces page

#### Scenario: Turn running
- **WHEN** the owner deletes a thread while its turn is still running
- **THEN** the response is 409 saying a reply is still being written, and the thread is unchanged

#### Scenario: Unknown thread
- **WHEN** the owner deletes a thread id that does not exist
- **THEN** the response is 404

#### Scenario: Not signed in
- **WHEN** the delete route is called without the session cookie
- **THEN** the response is 401
