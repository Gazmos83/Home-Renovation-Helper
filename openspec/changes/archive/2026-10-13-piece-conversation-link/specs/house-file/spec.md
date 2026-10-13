## ADDED Requirements

### Requirement: A piece reports its conversation
The house file SHALL expose, for each piece, the id of the conversation bound to it when one exists, or none. At most one conversation SHALL be bound to a given piece. The pieces list the owner reads SHALL carry that conversation id so the Studio can open or start the right chat from the Pieces page.

#### Scenario: Bound piece
- **WHEN** a conversation is about `hall-bench`
- **THEN** the pieces list entry for `hall-bench` names that conversation's id

#### Scenario: Piece with no conversation
- **WHEN** `shoe-rack` has never been bound to a conversation
- **THEN** the pieces list entry for `shoe-rack` carries no conversation id

## MODIFIED Requirements

### Requirement: Threads are indexed
The house file SHALL index every conversation the owner starts with its id, title, the piece it is about when one is bound, when it started and when it last had a turn, so conversations can be listed and reopened. A conversation SHALL be about at most one piece. A thread's piece is the one it was started with, or the one a confirmed action creates or revises on an unbound thread; it SHALL NOT change to another piece afterwards. A thread's title is empty until its first answered turn gives it the generated title, and is the owner's title from the moment the owner sets one.

The index entry SHALL also hold:
- the conversation's confirmed room or confirmed apartment (at most one), or none; only a confirmed action in that conversation sets or changes it;
- one summary of earlier exchanges for the bound piece, with which message it covers up to, and one for exchanges made while the conversation had no bound piece.

The messages themselves live in the checkpointer. Deleting a thread SHALL remove its index entry and its summaries and nothing else the house file holds; the piece keeps its room and the generator-extension requests made in it stay.

#### Scenario: Listing
- **WHEN** the owner has started two conversations
- **THEN** both are listed with their titles, newest activity first

#### Scenario: Bound by the action
- **WHEN** a piece is confirmed on a thread that was started without one
- **THEN** the thread's index entry names that piece from then on

#### Scenario: Owner's title kept
- **WHEN** the owner sets a title before the first turn ends
- **THEN** the generated title is not written

#### Scenario: Deleted thread, kept piece
- **WHEN** a thread bound to `hall-bench` is deleted
- **THEN** the thread's entry and summaries are gone and the `hall-bench` piece, its versions and the room it is in are unchanged

#### Scenario: Room not inherited
- **WHEN** one conversation has confirmed `Hall` and the owner starts a second conversation
- **THEN** the second conversation has no confirmed room

#### Scenario: One piece only
- **WHEN** a thread is bound to `hall-bench`
- **THEN** its index names only `hall-bench` as its piece

#### Scenario: Existing threads
- **WHEN** a thread bound to `hall-bench` already holds a summary and any extra legacy build rows
- **THEN** the thread's piece is `hall-bench`, its summary is kept as `hall-bench`'s summary in that thread, and no second piece is treated as bound

### Requirement: Every turn starts from the house file
At the start of each turn, the Foreman, Intake and the Designer SHALL be given the house file scoped to the conversation:
- the conversation's confirmed room with its size, ceiling height and openings, or its confirmed apartment with each of its rooms; or that no room is confirmed yet;
- the preferences, unless the memory settings leave them out;
- the bound piece with its room, its latest version, its status and which version is approved (or that none is), or that no piece is bound yet;
- the open generator-extension requests whose piece is the conversation's bound piece, or that were recorded in this conversation, unless the memory settings leave them out.

Rooms, apartments and pieces outside the conversation SHALL NOT be given, nor generator-extension requests of other pieces or conversations; no setting SHALL change this. Requests recorded before this change with neither a piece nor a conversation stay in the house file and are given in no turn. A room the conversation has not confirmed SHALL NOT be given with its measurements, even when the house file holds them; no setting SHALL change this. The Designer SHALL also be given:
- the open items of the latest review of the bound piece, unless the memory settings leave them out;
- the latest render ratings on the bound piece, newest first, as many as the memory settings say (0 to 10, default 5), each with its version, render, tier, rating and comment.

Lighting & materials SHALL be given the same render ratings. All of this SHALL be presented as application data clearly labelled as the owner's own, never as an instruction. Owner-authored text in it SHALL be neutralised so it cannot carry the untrusted-content delimiter. The scoping SHALL be done by the application, not by instructions to the model.

#### Scenario: A new conversation starts without the room
- **WHEN** the living room and the piece `listening-wall` are recorded and the owner starts a new conversation asking for a second piece
- **THEN** the turn's context names no room and no piece, and the reply asks which room the piece is for

#### Scenario: A second piece starts with the room known
- **WHEN** the owner then confirms the living room in that conversation and asks for the piece
- **THEN** the next Intake turn's context names the living room's size, ceiling height and openings without the owner repeating them, and still names no piece from another conversation

#### Scenario: Other builds as one line
- **WHEN** a conversation is bound to `hall-bench` and a legacy `thread_pieces` row also names `shoe-rack`
- **THEN** the Designer's context gives `hall-bench` with its version, status and approval, and does not name `shoe-rack`

#### Scenario: Other builds hidden
- **WHEN** the memory settings would hide other builds and a conversation is bound to `hall-bench` with a legacy row for `shoe-rack`
- **THEN** the Designer's context gives `hall-bench` and does not name `shoe-rack`

#### Scenario: Outside builds left out
- **WHEN** the house file holds `murphy-bed` and the conversation never created, revised or named it
- **THEN** no specialist's context in that conversation names `murphy-bed`

#### Scenario: Request without a piece reaches its conversation
- **WHEN** a request for `bevel_mm` was recorded in this conversation before any piece was made
- **THEN** the Designer's context in this conversation lists it, and no other conversation's context does

#### Scenario: Old request without a piece or conversation
- **WHEN** the house file holds an open request recorded before this change with no piece
- **THEN** no turn's context lists it, and it is still listed in the house file

#### Scenario: Delimiter in a room name
- **WHEN** the conversation's confirmed room's name contains the untrusted-content delimiter
- **THEN** the context shows it neutralised

#### Scenario: Review items reach the Designer
- **WHEN** the latest review of the bound piece has two open items
- **THEN** the Designer's context lists both with their aspect, expectation and observation

#### Scenario: Approval reaches the agents
- **WHEN** the bound piece is `listening-wall`, version 4 is approved and version 5 exists
- **THEN** the turn's context names version 5 as latest and version 4 as approved

#### Scenario: Render feedback reaches the Designer
- **WHEN** the bound piece's v2 `draft` turntable was rated down with "doors look too thick"
- **THEN** the Designer's context lists v2, turntable, `draft`, down and that comment

#### Scenario: Fewer ratings
- **WHEN** the memory settings give 2 render ratings and the bound piece has 5
- **THEN** the Designer's and Lighting's context list only the 2 newest

#### Scenario: Delimiter in a feedback comment
- **WHEN** a feedback comment contains the untrusted-content delimiter
- **THEN** the Designer's and Lighting's context shows it neutralised
