## MODIFIED Requirements

### Requirement: Threads are started, listed and read
The owner SHALL be able to start a conversation (optionally naming the piece it is about, and with or without a title), list conversations, read one conversation's messages and pending item, rename a conversation, and delete one. A thread id SHALL be issued by the service, never chosen by the client, and every thread route SHALL require the owner's session. A thread started without a title SHALL be given one after its first answered turn, written by the Foreman slot's model in three to six words from the owner's first message; the call SHALL be counted against that model's token budget like any other, and when it is refused or fails the title SHALL be the first words of the owner's message (at most 60 characters, cut at a word boundary). A title the owner has set SHALL never be replaced. Deleting a thread SHALL remove its index entry, its conversation memory, its tool settings, its uploads and its summary, and SHALL leave pieces, versions, rooms, preferences, reviews and recorded usage unchanged. A delete SHALL be refused, saying a reply is still being written, while a turn runs on the thread.

#### Scenario: Start and read
- **WHEN** the owner starts a thread and sends one turn
- **THEN** reading the thread returns the owner's message, the reply and nothing pending

#### Scenario: Not signed in
- **WHEN** a thread route is called without the session cookie
- **THEN** the response is 401

#### Scenario: Title from the first message
- **WHEN** the owner starts a thread with no title and sends "I want a listening wall for my records in the living room"
- **THEN** after the reply the thread has a title of three to six words from the Foreman's model, and the thread list shows it

#### Scenario: Title call refused
- **WHEN** the Foreman's model has reached its daily ceiling when the first turn of an untitled thread ends, and the owner's first message was "I want a listening wall for my records in the living room next to the window"
- **THEN** the thread's title is "I want a listening wall for my records in the living room", the message cut at a word boundary to at most 60 characters, and the turn's reply is unaffected

#### Scenario: Rename
- **WHEN** the owner renames a thread to "Listening wall"
- **THEN** the thread and the list show "Listening wall", and no later turn changes it

#### Scenario: Delete a conversation with a piece
- **WHEN** the owner deletes a thread that created `listening-wall` versions 1 to 4 and holds two uploads
- **THEN** the thread is gone from the list, reading it answers 404, its uploads are no longer served, and `listening-wall` with all four versions is still in the house file and on the Pieces page

#### Scenario: Unknown thread
- **WHEN** the owner deletes or renames a thread id that does not exist
- **THEN** the response is 404

### Requirement: A confirmation pauses the turn until the owner answers
When a gated action is proposed — confirmed numbers, a new piece, a revision, a `final` render — or a specialist asks the owner questions through `ask_owner`, the turn SHALL pause and the reply SHALL carry the pending item with a stable id and its kind. A confirmation carries a subject, a readable summary and the structured proposal, and the owner answers it with `yes` or `no` and an optional reason; `yes` runs the action and `no` returns the reason to the specialist, which continues the conversation. A question set carries its questions in order, each with its text and, when given, a unit and a list of choices; the owner answers it with one answer per question, or declines it with a message in their own words, and the specialist continues with the answers (or the message) in the same turn. An answer naming no pending item, a stale id, an answer of the wrong kind, or a question set answered with a different number of answers SHALL be refused (409 for no pending item or a stale id, 422 for the shape) and nothing runs. A new message while anything is pending SHALL be refused with 409 naming what is pending.

#### Scenario: Revision confirmed
- **WHEN** the Designer proposes "cabinet: 2 shelves → 3" and the owner answers `yes`
- **THEN** the revision is created and the reply reports the new version

#### Scenario: Declined with a reason
- **WHEN** the owner answers `no` with "make it 4 shelves"
- **THEN** nothing is created and the next reply proposes a changed revision

#### Scenario: Stale answer
- **WHEN** the owner answers a pending id that is no longer pending
- **THEN** the response is 409 and nothing runs

#### Scenario: Questions answered
- **WHEN** Intake asks "Ceiling height?" (unit mm) and "Budget?" (unit EUR) and the owner answers 2500 and 900
- **THEN** Intake continues the same turn with both answers, and the thread's history shows the two questions with their answers

#### Scenario: Wrong number of answers
- **WHEN** the owner answers a set of two questions with one answer
- **THEN** the response is 422 and the questions stay pending

#### Scenario: Questions declined
- **WHEN** the owner declines the questions with "I'll measure tomorrow"
- **THEN** the specialist continues with that message and nothing is pending afterwards

## ADDED Requirements

### Requirement: A turn can be followed while it runs
The turn and the confirmation answer SHALL each also be offered as a stream of events that reports, in order: each specialist as it starts (by role name only), each tool as it starts (by its plain plugin name only), and then exactly one ending event — the reply with the specialists that ran, the pending item, or a failure with its class and reason. A title written after the first turn SHALL be reported as its own event before the stream closes. Refusals decided before the turn runs — no session, unknown thread, memory unavailable, something already pending, a bad upload id — SHALL answer with the same status and body as the non-streamed route and open no stream. A gateway failure during the turn SHALL end the stream with a failure event carrying the class and reason, and SHALL leave the unanswered message out of the thread exactly as the non-streamed route does. No event SHALL carry a model name or slug, a prompt, a token count, a cost, a tool's arguments or a file-system path. The non-streamed routes SHALL keep their current behaviour.

#### Scenario: Followed turn
- **WHEN** the owner sends "make it 2206 mm wide" on the streamed route and the Foreman routes to the Designer, which calls `revise_package`
- **THEN** the stream reports the Designer starting, then `revise package` starting, then the pending revision, and nothing else

#### Scenario: Refused before running
- **WHEN** a confirmation is pending and the owner sends a message on the streamed route
- **THEN** the response is 409 naming the pending subject and no stream is opened

#### Scenario: Gateway timeout while streaming
- **WHEN** the Designer's model call times out during a streamed turn
- **THEN** the stream ends with a failure event of class `timeout`, and reading the thread does not show the unanswered message

#### Scenario: No internals in events
- **WHEN** any streamed turn completes
- **THEN** no event contains a model slug, a token figure, a tool argument or a host path

### Requirement: Replies follow the formatting rules
Every specialist's instructions SHALL include, composed by code after its editable text and before the untrusted-content guard, the rules that its questions to the owner are a bullet list (one question per bullet), any list of items with sizes or quantities (a cut list, parts, hardware, prices) is a table, decisions taken in the conversation are listed as a table when summarised, and arithmetic the owner should check is written in a fenced block marked `calc`. The rules SHALL not apply to `ask_owner` questions, which are structured.

#### Scenario: Rules composed
- **WHEN** the Designer's prompt is assembled
- **THEN** it contains the formatting rules once, after the instruction text and before the guard

#### Scenario: Not editable
- **WHEN** the developer edits the Designer's instruction text
- **THEN** the formatting rules are still composed after it unchanged
