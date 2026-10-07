## MODIFIED Requirements

### Requirement: Threads are indexed
The house file SHALL index every conversation the owner starts with its id, title, the piece it is about when one is bound, when it started and when it last had a turn, so conversations can be listed and reopened. A thread's piece is the one it was started with until a confirmed action creates or revises a piece in it, after which it is that piece. A thread's title is empty until its first answered turn gives it the generated title, and is the owner's title from the moment the owner sets one. The index entry SHALL also hold the thread's summary of earlier exchanges, when one has been made, and which message it covers up to. The messages themselves live in the checkpointer. Deleting a thread SHALL remove its index entry and summary and nothing else the house file holds.

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
- **THEN** the thread's entry is gone and the `hall-bench` piece, its versions and the room it is in are unchanged
