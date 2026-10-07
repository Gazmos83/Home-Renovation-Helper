## MODIFIED Requirements

### Requirement: Threads are indexed
The house file SHALL index every conversation the owner starts with its id, title, the piece it is about when one is bound, when it started and when it last had a turn, so conversations can be listed and reopened. A thread's piece is the one it was started with until a confirmed action creates or revises a piece in it, after which it is that piece. The messages themselves live in the checkpointer.

#### Scenario: Listing
- **WHEN** the owner has started two conversations
- **THEN** both are listed with their titles, newest activity first

#### Scenario: Bound by the action
- **WHEN** a piece is confirmed on a thread that was started without one
- **THEN** the thread's index entry names that piece from then on
