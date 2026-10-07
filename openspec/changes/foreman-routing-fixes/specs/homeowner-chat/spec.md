## ADDED Requirements

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
