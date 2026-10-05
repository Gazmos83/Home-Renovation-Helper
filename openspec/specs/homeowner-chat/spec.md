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
