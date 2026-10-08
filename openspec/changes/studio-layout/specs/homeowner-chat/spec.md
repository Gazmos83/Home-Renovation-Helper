## MODIFIED Requirements

### Requirement: A thread's history shows every reply the owner was meant to read
Reading a thread SHALL return, in order, the owner's messages, every assistant message that has text (including one sent together with tool calls), one `confirmation` entry per answered confirmation carrying its subject, its summary and the owner's answer (with the reason when one was given), and one `notice` entry per render notice posted to the thread. A notice SHALL come after every message the thread held when it was posted. A `notice` entry SHALL carry its text, its outcome (`succeeded` or `failed`) and the render's tier, and, for a render of a piece version, the piece's id and the version. Tool calls, tool arguments and tool results SHALL NOT appear. An assistant message with tool calls and no text SHALL NOT produce an entry. The entries SHALL obey the no-internals rule.

#### Scenario: Text sent with a tool call is shown
- **WHEN** the Designer replies "Here's how your spec forces the dimensions…" and calls `create_piece` in the same message
- **THEN** reading the thread returns that text as an assistant entry, and no entry contains the tool's arguments

#### Scenario: Answered confirmation stays visible
- **WHEN** the owner answers `no` with the reason "make it 4 shelves" to a pending revision
- **THEN** reading the thread returns a `confirmation` entry with the subject `revise`, the summary the owner was shown and the answer `no` with that reason, before the reply that followed

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

## ADDED Requirements

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
- **WHEN** a preview turntable of `hall-bench` version 2 started from a conversation fails
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
