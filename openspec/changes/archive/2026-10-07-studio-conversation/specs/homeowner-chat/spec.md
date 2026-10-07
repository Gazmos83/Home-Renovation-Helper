## ADDED Requirements

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
