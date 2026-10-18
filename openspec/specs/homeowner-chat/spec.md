# homeowner-chat Specification

## Purpose
Defines how the homeowner talks to the Foreman: conversations as threads, one turn at a time, a pending confirmation that pauses a turn until the owner answers, what the homeowner may see, and how a turn is traced and refused.

## Requirements

### Requirement: Threads are started, listed and read
The owner SHALL be able to start a conversation (optionally naming the piece it is about, and with or without a title), list conversations, read one conversation's messages and pending item, rename a conversation, and delete one. A thread id SHALL be issued by the service, never chosen by the client, and every thread route SHALL require the owner's session. Starting a conversation that names an existing piece SHALL bind that thread to the piece at once. Starting a conversation for a piece that already has a conversation SHALL be refused, naming that the piece already has a conversation. A thread started without a title SHALL be given one after its first answered turn, written by the Foreman slot's model in three to six words from the owner's first message; the call SHALL be counted against that model's token budget like any other, and when it is refused or fails the title SHALL be the first words of the owner's message (at most 60 characters, cut at a word boundary). A title the owner has set SHALL never be replaced. Deleting a thread SHALL remove its index entry, its conversation memory, its tool settings, its uploads and its summary, and SHALL leave pieces, versions, rooms, preferences, reviews and recorded usage unchanged. A delete SHALL be refused, saying a reply is still being written, while a turn runs on the thread.

#### Scenario: Start and read
- **WHEN** the owner starts a thread and sends one turn
- **THEN** reading the thread returns the owner's message, the reply and nothing pending

#### Scenario: Start bound to an existing piece
- **WHEN** the owner starts a thread naming `hall-bench` and that piece has no conversation yet
- **THEN** reading the thread shows it is about `hall-bench`

#### Scenario: Piece already has a conversation
- **WHEN** `hall-bench` already has a conversation and the owner starts a thread naming `hall-bench`
- **THEN** the start is refused saying the piece already has a conversation, and no new thread is created

#### Scenario: Not signed in
- **WHEN** a thread route is called without the session cookie
- **THEN** the response is 401

#### Scenario: Title from the first message
- **WHEN** the owner starts a thread with no title and sends "I want a listening wall for my records in the living room"
- **THEN** after the reply the thread has a title of three to six words from the Foreman's model, and listing conversations shows it

#### Scenario: Title call refused
- **WHEN** the Foreman's model has reached its daily ceiling when the first turn of an untitled thread ends, and the owner's first message was "I want a listening wall for my records in the living room next to the window"
- **THEN** the thread's title is "I want a listening wall for my records in the living room", the message cut at a word boundary to at most 60 characters, and the turn's reply is unaffected

#### Scenario: Rename
- **WHEN** the owner renames a thread to "Listening wall"
- **THEN** the thread shows "Listening wall", and no later turn changes it

#### Scenario: Delete a conversation with a piece
- **WHEN** the owner deletes a thread that created `listening-wall` versions 1 to 4 and holds two uploads
- **THEN** reading it answers 404, its uploads are no longer served, and `listening-wall` with all four versions is still in the house file and on the Pieces page

#### Scenario: Unknown thread
- **WHEN** the owner deletes or renames a thread id that does not exist
- **THEN** the response is 404

### Requirement: A turn is one message in, one reply out
Sending a message to a thread SHALL run exactly one Foreman turn and answer with the reply text, which specialist answered (by role name only), and either nothing pending or a pending confirmation. The turn SHALL be bounded: after the configured number of tool rounds the specialist answers in text with no further tool calls, and every model call in it is fitted to its model's token budget before it is sent.

#### Scenario: Plain turn
- **WHEN** the owner writes "I want a bench for the hall"
- **THEN** the reply is text from Intake and nothing is pending

#### Scenario: Round cap
- **WHEN** a specialist would call tools more times than the cap allows
- **THEN** the turn ends with a text reply that says what remains undone

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
Reading a thread SHALL return, in order, the owner's messages, every assistant message that has text (including one sent together with tool calls), one `confirmation` entry per answered confirmation, and one `notice` entry per render notice posted to the thread. A `confirmation` entry SHALL carry its subject, its plain title, its summary, the owner's answer (with the reason when one was given) and, when the confirmation had one, its table of calculations (column names and rows). The plain title SHALL be composed by the application from the subject, with no model call. Each subject SHALL have a fixed title in plain words (for example "Composing room" for a room change, "Revising piece" for a revision, "Importing design" for a design import), and an unknown subject SHALL be titled "Confirmation". No title, row or summary shown to the owner SHALL contain a tool's internal name. A notice SHALL come after every message the thread held when it was posted. A `notice` entry SHALL carry its text, its outcome (`succeeded` or `failed`) and the render's tier, and, for a render of a piece version, the piece's id and the version. Tool calls, tool arguments and tool results SHALL NOT appear. An assistant message with tool calls and no text SHALL NOT produce an entry. The entries SHALL obey the no-internals rule.

#### Scenario: Text sent with a tool call is shown
- **WHEN** the Designer replies "Here's how your spec forces the dimensions…" and calls `create_piece` in the same message
- **THEN** reading the thread returns that text as an assistant entry, and no entry contains the tool's arguments

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

### Requirement: A thread reports its piece's progress
The owner SHALL be able to read, on a thread, where the piece it is about stands: whether a brief is confirmed, whether a piece exists and its latest version with that version's build state, whether a render of that version is queued or running, whether that version has a screenshot, a draft or preview render, a review (with the count of open items), a detail pass, and a final render, and which of these is the next step the owner can ask for. The read SHALL also list the piece's open generator-extension requests by field and the owner's words. A thread with no bound piece SHALL report only the brief state and the next step. The read SHALL be derived from the house file, the version folder and the thread's own conversation state, and SHALL contain no model name, prompt, token count, cost or file-system path; an image is named by its package route, and so is the latest version's turntable viewer when its turntable is published.

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

#### Scenario: Render running
- **WHEN** a draft turntable of the latest version is queued or running
- **THEN** the progress says a render is running; once it has finished or failed it says none is

### Requirement: A turn binds the thread to the piece it creates or revises
When a confirmed action creates a piece or revises one on a thread with no bound piece, the thread SHALL be bound to that piece, so the thread's list entry and later turns name it. When the thread is already bound to a piece, a confirmed action that would create a different piece, or revise a different piece, SHALL be refused in plain words naming the bound piece, and SHALL change no binding. Naming another house-file piece in the owner's message SHALL NOT bind the thread to it or switch the piece. A declined or failed action SHALL bind nothing.

#### Scenario: Created in the conversation
- **WHEN** the owner confirms a new piece `hall-bench` on a thread started without a piece
- **THEN** reading the thread shows it is about `hall-bench`

#### Scenario: Revised on an unbound thread
- **WHEN** the owner confirms a revision of `hall-bench` on a thread with no piece
- **THEN** the thread is about `hall-bench`

#### Scenario: A second piece
- **WHEN** a thread about `hall-bench` would confirm a new piece `shelf`
- **THEN** the action is refused naming that the conversation is about `hall-bench`, the thread stays about `hall-bench`, and no second build is recorded

#### Scenario: Declined
- **WHEN** the owner answers `no` to a new piece
- **THEN** the thread's piece is unchanged

#### Scenario: Switch by name
- **WHEN** a thread about `hall-bench` has the owner write "back to the shoe rack: make it 900 mm" naming `shoe-rack`
- **THEN** the thread stays about `hall-bench` and `shoe-rack` is not bound

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

### Requirement: A render started in a thread posts a notice when it ends
When a render that a specialist's tool started in a thread ends, the service SHALL post one notice to that thread. This covers stills and turntables at every tier, of a piece version (alone or placed in a room), of an apartment shell, of a composition, and of a detail pass. The notice is written by code, not by a model.

- A finished render's notice SHALL name the tier, the kind and what was rendered, and say it is ready, for example "The draft turntable of hall-bench version 1 is ready." For a piece version it SHALL add that the result can also be checked in the Project panel.
- A failed render's notice SHALL say in plain words that it did not finish and that nothing new was published, for example "The draft turntable of hall-bench version 1 did not finish, so nothing new was published. You can ask for it again." It SHALL NOT carry the error text.
- A render started from a Studio page rather than a conversation SHALL post no notice. A render whose thread was deleted before it ended SHALL post nothing and SHALL still finish as it would have.
- Posting a notice SHALL NOT change the render's outcome; a failure to post SHALL be logged and the render's outcome kept.
- A notice SHALL NOT be sent to any model as part of the conversation, and SHALL obey the no-internals rule.

#### Scenario: Draft finished
- **WHEN** the Builder starts a draft turntable of `hall-bench` version 1 from a conversation and it finishes
- **THEN** the thread holds a notice with outcome `succeeded`, package `hall-bench`, version 1, saying the draft turntable is ready and can also be checked in the Project panel

#### Scenario: Final finished
- **WHEN** the owner approves a final still of `hall-bench` version 3 and it finishes
- **THEN** the thread holds a notice with outcome `succeeded`, package `hall-bench` and version 3, naming the final still

#### Scenario: Render failed
- **WHEN** a draft turntable of `hall-bench` version 2 started from a conversation fails
- **THEN** the thread holds a notice with outcome `failed` saying it did not finish, and the notice contains no error text, host path or model slug

#### Scenario: Started from the Studio
- **WHEN** a draft still is started from the Studio's render route
- **THEN** no thread gets a notice

#### Scenario: Thread deleted meanwhile
- **WHEN** the conversation is deleted while its render runs
- **THEN** the render finishes and publishes as usual and no notice is written

#### Scenario: Not sent to the model
- **WHEN** the owner sends a message after a notice was posted
- **THEN** the specialist's model call contains no message with the notice's text

### Requirement: A running turn can be stopped
The owner SHALL be able to stop the thread's running turn through an owner-gated route. A stopped turn SHALL end at the next step boundary: before the next model call or tool call. It SHALL end the stream with a `stopped` event. A stopped turn SHALL be discarded: reading the thread afterwards shows the history as it was before the owner's message. A tool call that completed before the stop SHALL NOT be undone. If one completed, the `stopped` event SHALL say so in plain words (for example "a build was already started"). A stop SHALL be answered with 409 when no turn is running, 404 for an unknown thread and 401 without the session cookie. A confirmation that is pending is not a running turn; it is answered as before.

#### Scenario: Stopped before any tool
- **WHEN** the owner sends "make it wider" and stops the turn while the Foreman is choosing
- **THEN** the stream ends with `stopped`, and reading the thread shows neither "make it wider" nor a reply

#### Scenario: Stopped after a build started
- **WHEN** the owner stops a turn after the Builder's build tool has started a build
- **THEN** the stream ends with `stopped` saying a build was already started, the build continues, and the turn is not in the thread's history

#### Scenario: Nothing running
- **WHEN** the owner stops a thread with no running turn
- **THEN** the answer is 409 and the thread is unchanged

### Requirement: The owner's latest message can be edited and sent again
The owner SHALL be able to replace the thread's latest owner message with new text through an owner-gated route, when no turn is running and no confirmation is pending. The thread SHALL be rewound to just before that message, removing it and every reply after it. The new text SHALL then run as a turn, streamed like any turn. Only the latest owner message SHALL be editable. Pieces, versions, renders, compositions and house-file writes made by the rewound turn SHALL stay. A rewound turn that confirmed one of them SHALL be named in the edit response, so the owner is told. Uploads attached to the replaced message SHALL be attached to the new one.

#### Scenario: Message corrected
- **WHEN** the owner's latest message was "make it 60 cm deep", the reply asked a question, and the owner edits it to "make it 45 cm deep"
- **THEN** the thread shows "make it 45 cm deep" and its new reply, and neither the old message nor the old reply

#### Scenario: Version already created
- **WHEN** the latest owner message's turn created `bench` v3 after a confirmed `yes` and the owner edits that message
- **THEN** the response names `bench` v3 as staying, and v3 still exists after the edited turn

#### Scenario: Older message
- **WHEN** the owner tries to edit a message that is not the latest owner message
- **THEN** the answer is 409 and the thread is unchanged

#### Scenario: Confirmation pending
- **WHEN** a confirmation is pending and the owner tries to edit the latest message
- **THEN** the answer is 409 naming the pending subject

### Requirement: A build started in a thread posts a notice when it ends
When a build of a piece version that a specialist's tool started in a thread ends, the service SHALL post one build notice to that thread. This covers builds started by creating a piece, by a revision, by a rebuild, and by the Builder's build tool. The notice SHALL be written by code, not by a model, and SHALL carry the piece and version.
- A finished build's notice SHALL say that the version is built, for example "hall-bench version 2 is built."
- A failed build's notice SHALL say in plain words that the version did not build, for example "hall-bench version 2 did not build. You can ask for it again." It SHALL NOT carry the error text.

A revision, rebuild or design import that creates a version SHALL post no notice of its own when the version is recorded; the build notice is that version's one notice. A build started from a Studio route SHALL post no notice. A build whose thread was deleted before it ended SHALL post nothing and SHALL still finish. Posting SHALL NOT change the build's outcome; a failure to post SHALL be logged. A build notice, like a render notice, SHALL NOT be sent to any model and SHALL obey the no-internals rule. Render notices SHALL be unchanged.

#### Scenario: Revision built
- **WHEN** the owner confirms a revision of `hall-bench` in a conversation and version 2 builds
- **THEN** the thread holds a build notice with outcome `succeeded`, package `hall-bench` and version 2, saying it is built

#### Scenario: Build failed
- **WHEN** version 2 of `hall-bench`, started from a conversation, fails to build
- **THEN** the thread holds a build notice with outcome `failed` saying it did not build, with no error text, host path or model slug

#### Scenario: Started from the Studio
- **WHEN** the owner submits an edited spec to the package route
- **THEN** no thread gets a build notice

#### Scenario: Not sent to the model
- **WHEN** the owner sends a message after a build notice was posted
- **THEN** the specialist's model call contains no message with the notice's text

#### Scenario: No separate revision notice
- **WHEN** the owner confirms a revision of `hall-bench` in a conversation and version 2 is recorded
- **THEN** no notice is posted until its build ends, and then exactly one build notice for version 2 is posted

### Requirement: A thread's progress names its room and the room's 3D view
The thread progress read SHALL report the conversation's confirmed room or apartment, or nothing when the conversation has confirmed neither. When one is confirmed the read SHALL give its name and its scope (`room` or `apartment`), and whether its composition's latest version has a 3D model. When it has one, the read SHALL give the composition's slug and name the model and the surface map by their composition routes. When a composition exists the read SHALL also list its newest five versions, newest first, each with its number, build status, and, when that version has `model.glb`, its model, surface map and dimensions by their composition routes. The read SHALL report only this conversation's own room or apartment, never one confirmed in another conversation or the room a piece is assigned to, and SHALL contain no file-system path.

#### Scenario: No room confirmed
- **WHEN** the owner reads the progress of a thread that has confirmed no room or apartment
- **THEN** the progress reports no room

#### Scenario: Room without a composition
- **WHEN** the thread has confirmed room `Hall` and `Hall` has no composition
- **THEN** the progress names `Hall` with scope `room` and reports no 3D model

#### Scenario: Room with a 3D view
- **WHEN** the thread has confirmed room `Hall` and composition `Hall`'s latest version has `model.glb` and its surface map
- **THEN** the progress names `Hall`, gives the composition's slug, and names the model and the surface map by their composition routes

#### Scenario: Latest version without a model
- **WHEN** composition `Hall`'s latest version was built before models were published and has no `model.glb`
- **THEN** the progress names `Hall` and reports no 3D model

#### Scenario: Apartment scope
- **WHEN** the thread has confirmed apartment `Flat` and composition `Flat` has a 3D model
- **THEN** the progress names `Flat` with scope `apartment` and gives its composition's slug and routes

#### Scenario: Another conversation's room
- **WHEN** the thread has confirmed no room, another thread has confirmed `Hall`, and the thread's piece is assigned to `Hall`
- **THEN** the progress reports no room

#### Scenario: Newest five versions
- **WHEN** the thread has confirmed `Hall` and composition `Hall` has versions 1 to 6, of which version 2 has no `model.glb`
- **THEN** the progress lists versions 6, 5, 4, 3 and 2, each of 6 to 3 with its model, surface map and dimensions routes, and version 2 with none

### Requirement: The owner reads, corrects and compresses the conversation's notes
Beside the chat, the owner SHALL see a "Decisions so far" panel holding the note for the active build, or the conversation's own note when no build is active, or that there is none yet. The owner SHALL be able to edit and save the note; a saved edit SHALL be marked as the owner's and used as written from the next call. The panel SHALL offer a "compress now" action, as set out in the token-budget spec. The panel SHALL NOT show tokens, budgets, models or costs. Saved note text SHALL be neutralised so it cannot carry the untrusted-content delimiter. The routes SHALL require the owner's session and SHALL answer 404 for another thread's id that does not exist.

#### Scenario: Note shown
- **WHEN** the active build `hall-bench` has a stored note
- **THEN** the panel shows that note, and no token figure or model name

#### Scenario: No note yet
- **WHEN** the conversation has never been compressed
- **THEN** the panel says there is no note yet and offers "compress now"

#### Scenario: Owner edits the note
- **WHEN** the owner changes "doors: hinged" to "doors: push-latch" and saves
- **THEN** the next call sends the edited note, marked as the owner's

#### Scenario: Delimiter in an edited note
- **WHEN** the owner's edited note contains the untrusted-content delimiter
- **THEN** it is stored and sent neutralised

#### Scenario: Without a login
- **WHEN** the note route is called without the owner's session
- **THEN** it answers 401

### Requirement: The chat's room measurements match the approved room version
The room block the Foreman and specialists receive for the conversation's confirmed room SHALL state each wall's length and each ceiling height as the inspector view shows them, read from the stored document of the room's approved composition version and labelled with that version number. When the room has no approved version it SHALL use the latest version and say that it is not approved; when it has no composition it SHALL state the house-file figures as today. The block SHALL be rebuilt on every turn, so approving a version changes the figures from the next turn without any action by the owner. The prompt SHALL tell the model to prefer this block over measurements it quoted earlier or that appear in the conversation note.

#### Scenario: Irregular room quoted by wall
- **WHEN** Wohnen version 2 is approved and the owner asks how long the walls are
- **THEN** the reply gives wall 1 to wall 5 as 6200, 5700, 2700, 2241 and 6199 mm and the ceiling as 2500 mm, naming version 2, with no bounding-box figure presented as a wall length

#### Scenario: New version approved
- **WHEN** the owner approves Wohnen version 3, whose wall 3 is 2900 mm, and sends the next message
- **THEN** the room block names version 3 and wall 3 as 2900 mm, and the reply does not repeat version 2's 2700 mm

#### Scenario: No approved version
- **WHEN** Wohnen has versions 1 and 2 and none is approved
- **THEN** the block uses version 2 and states that it is not approved

### Requirement: The chat can read a room version's inspector dimensions
The chat SHALL be able to read the wall lengths and ceiling heights of a named room version, the same figures the inspector view's dimensions switch shows, so that it can confirm or correct a figure the owner or the bot quoted. The read SHALL be read-only, SHALL be limited to the conversation's confirmed room, and SHALL never change a dimension, the house file or a spec.

#### Scenario: Confirm a figure
- **WHEN** the owner says "the inspector shows 2241 on wall 4, you said 2300" about version 2
- **THEN** the bot reads version 2's dimensions, confirms wall 4 is 2241 mm and corrects its earlier figure in the reply

#### Scenario: Other room refused
- **WHEN** the bot is asked for the dimensions of a room outside the conversation's confirmed room
- **THEN** the read is refused with a stated reason and nothing is returned

### Requirement: Approving a version drops rows that only record an older version being saved
When the owner approves a version of a piece, the system SHALL remove from the "decisions so far" note of every conversation bound to that piece each row that only records an older version of that piece (a lower number than the approved one) being saved, created or built. A row that states a decision or a reason, a row that names no older version, and a row about another piece SHALL be kept as written. The system SHALL NOT delete or change any version, folder, review, render or record, SHALL NOT call a model, and SHALL NOT save a note that would be left with no rows. Approving a version that is already approved SHALL change no note.

#### Scenario: Older saved rows are dropped
- **WHEN** version 3 of `listening-wall` is approved and the note holds "Version 1 saved" and "Version 2 saved" rows
- **THEN** both rows are gone from the note, and versions 1 and 2 are still listed and openable

#### Scenario: A decision that names an older version is kept
- **WHEN** version 3 is approved and a row reads "Version 2 had the doors on top; moved to the bottom"
- **THEN** the row stays in the note

#### Scenario: The approved or a newer version is not dropped
- **WHEN** version 2 is approved and the note holds a "Version 3 saved" row
- **THEN** that row stays in the note

#### Scenario: Another piece's rows are kept
- **WHEN** version 3 of `listening-wall` is approved and a row says "Hall bench version 1 saved"
- **THEN** that row stays in the note

#### Scenario: Only rows would be left empty
- **WHEN** every row of the note records an older version being saved
- **THEN** the note is kept as it was

#### Scenario: Re-approving changes nothing
- **WHEN** an already approved version is approved again
- **THEN** no note changes

### Requirement: A plain question about the expected height gets a short reply
When the owner's message only asks what the expected, maximum or highest height is, the Foreman SHALL answer, by an application rule before any specialist or model call, with exactly: "The height is not verified. What should the height be?" That answer SHALL carry no engineering status text, source, missing-input list or legal note. A message that names strength, load, deflection, anchorage, safety or another engineering term, names a kitchen part, or asks about any other dimension SHALL be routed as before. The rule SHALL change no stored data.

#### Scenario: The short question
- **WHEN** the owner asks "What's expected height"
- **THEN** the reply is "The height is not verified. What should the height be?" and nothing else

#### Scenario: A longer or different question is routed as before
- **WHEN** the owner asks "What's the maximum height this cabinet can safely carry?"
- **THEN** the message is routed to the engineering path and not answered by this rule

#### Scenario: Another dimension
- **WHEN** the owner asks "What's the expected depth"
- **THEN** the rule does not apply

#### Scenario: Nothing is stored
- **WHEN** the rule answers
- **THEN** the brief, the note and the house file are unchanged

### Requirement: The owner changes the decisions note by asking in the chat
The owner SHALL be able to add, change or delete one row of the active "decisions so far" note by asking an assistant in the chat. An assistant SHALL change a row only when the owner's own message explicitly asks for it; it MAY offer to, but SHALL NOT change the note unprompted or as a side effect of another request. Before anything is written the chat SHALL show the row as it is now and as it will be, and SHALL wait for the owner's "yes"; any other answer SHALL change nothing. The write SHALL be the panel's save: text neutralised, within the note's size limit, never leaving the note empty, and marked as the owner's. The note's thread and active build SHALL come from the session, never from a value the model supplies. A row SHALL be named by its topic, with its position when two rows share a topic; an unknown or ambiguous name SHALL be refused with the matching rows listed, and nothing SHALL be written. Deleting the only row SHALL be refused. The tool SHALL be switchable per conversation like other plugins. The panel SHALL show the changed note when the turn ends. A change made this way SHALL NOT change any spec, figure, price or house-file record.

#### Scenario: Nothing changes unprompted
- **WHEN** the owner states a decision or asks something else without asking for the note to change
- **THEN** no confirmation is shown and the note is unchanged, though the assistant may offer to add the decision

#### Scenario: A row is deleted on request
- **WHEN** the owner asks the assistant to remove the "Doors" decision and answers "yes" to the shown change
- **THEN** that row is removed from the note, the note is marked as the owner's, and the panel shows the note without that row

#### Scenario: The owner declines
- **WHEN** the owner answers anything but "yes" to the shown change
- **THEN** the note is unchanged and the assistant says nothing was changed

#### Scenario: A row is changed or added
- **WHEN** the owner asks to note that the shelves are 18 mm and confirms
- **THEN** the row for the shelves is changed, or a new "Shelves" row is added when none exists, and no other row changes

#### Scenario: A name matches several rows
- **WHEN** the owner names a topic that two rows share and gives no position
- **THEN** the call is refused before any confirmation, listing the matching rows with their positions, and the note is unchanged

#### Scenario: A last row or an empty edit is refused
- **WHEN** the request would delete the only row, or leave a row's topic or decision empty
- **THEN** the call is refused with the reason and the note is unchanged

#### Scenario: Another conversation's note is out of reach
- **WHEN** the model names another thread or another build in the call
- **THEN** the value is ignored or refused, and only the session's active note can be changed

#### Scenario: The tool is switched off
- **WHEN** the owner has switched the tool off for the conversation
- **THEN** the assistant cannot call it and says the tool is off

### Requirement: The owner records a decision from a chat message
Each message in the chat SHALL offer an "Add to decisions" action, shown as a bold, framed, light-green button. It SHALL make one model call that compresses the message into a one-line decision and a suggested topic, and open a new row in the "decisions so far" table with only those two values (never the full message text), for the owner to edit, save or cancel. Saving SHALL add the row as the panel's "Add Topic Decision" does, with the same checks and the owner's mark, and without a model call. Nothing SHALL be saved before the owner saves. If the compression call fails or is refused, the row SHALL open empty with a plain-words message.

#### Scenario: A compressed decision is recorded from a message
- **WHEN** the owner chooses "Add to decisions" on a long message
- **THEN** the new row opens with a one-line decision and a suggested topic, not the full message; after the owner saves, that row is added to the end of the active note and the panel shows it

#### Scenario: The compression fails
- **WHEN** the compression call fails or a token ceiling refuses it
- **THEN** the row opens empty, a plain-words message is shown, and the note is unchanged

#### Scenario: The owner cancels
- **WHEN** the owner chooses "Add to decisions" and then cancels
- **THEN** the note is unchanged

#### Scenario: The button's look
- **WHEN** a chat message shows "Add to decisions"
- **THEN** the button is bold, framed and light green

### Requirement: An answered engineering question does not make later turns engineering turns
When a turn is routed to the engineering path, the owner's message of that turn SHALL belong to the engineering exchange together with its replies and tool results. Later routing and agent calls SHALL leave out the whole exchange, the question as well as the answer, as they already leave out its replies. A later message SHALL be an engineering turn only when its own text names an engineering term, or when the routing model flags that message itself. In conversations stored before this change, an owner message followed in its turn by an engineering reply SHALL count as part of that exchange, without changing stored data. The owner's chat view SHALL still show every message.

#### Scenario: The reported loop
- **WHEN** the owner asks "Will the bridge be structurally stable if the dividers are removed?", gets the engineering status reply, then writes "Keep and shorten the dividers."
- **THEN** the second message is not routed as an engineering turn by the earlier question, the Designer's reply reaches the owner, and the earlier question and its status reply are not in the second turn's requests

#### Scenario: A new engineering question still is one
- **WHEN** after an answered engineering question the owner asks "Can the shelf carry 30 kg?"
- **THEN** that turn is an engineering turn

#### Scenario: An existing looping conversation recovers
- **WHEN** a conversation stored before this change holds an unmarked owner question followed by an engineering status reply, and the owner sends a design request
- **THEN** the routing call does not contain that question, and the stored messages are unchanged

### Requirement: A room render started in a thread is followed and points to its result
When a specialist's tool starts a render of a room or apartment composition in a thread, the service SHALL record it against that thread. While it is queued or running, the thread's progress SHALL report `rendering`. A recorded render SHALL count only while that composition version's status shows it queued or running, so a record left behind by a failed process never keeps the thread rendering. The record SHALL be removed when the render's notice is posted.

The notice of a finished room render SHALL name the composition and version, and say that it can also be found on the Rooms page, for example "The draft turntable of wohnen version 11 is ready. You can also find it on the Rooms page." It SHALL store the composition and version. When the thread is read, the notice SHALL carry a link to its result: a turntable's viewer, labelled "Open the turntable viewer", or a still's image, labelled "Open the still". Each link uses the composition's file route, and is included only while its file exists. A failed room render's notice SHALL carry no link. A notice posted before this requirement SHALL carry none.

#### Scenario: Room render followed
- **WHEN** the owner asks in the Murphy bed conversation for a draft turntable of the Wohnen composition and it is running
- **THEN** that thread's progress reports `rendering`

#### Scenario: Stale record ignored
- **WHEN** a recorded room render's composition version shows no queued or running render
- **THEN** the thread's progress does not report `rendering` for it

#### Scenario: Turntable ready with a link
- **WHEN** the draft turntable of `wohnen` version 11 finishes
- **THEN** the thread holds a notice saying "The draft turntable of wohnen version 11 is ready. You can also find it on the Rooms page." with a link "Open the turntable viewer" to `/compositions/wohnen/versions/11/files/viewer.html`

#### Scenario: Still ready with a link
- **WHEN** the draft still of `wohnen` version 11 finishes
- **THEN** its notice carries a link "Open the still" to `/compositions/wohnen/versions/11/files/still.png`

#### Scenario: File gone
- **WHEN** `wohnen` version 11 is deleted after its notice was posted
- **THEN** reading the thread shows the notice with no link

#### Scenario: Failed room render
- **WHEN** a room turntable started in a conversation fails
- **THEN** its notice says it did not finish and carries no link
