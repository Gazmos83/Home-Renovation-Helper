## MODIFIED Requirements

### Requirement: A turn is one message in, one reply out
Sending a message to a thread SHALL run exactly one Foreman turn and answer with the reply text, which specialist answered (by role name only), and either nothing pending or a pending confirmation. The turn SHALL be bounded: after the configured number of tool rounds the specialist answers in text with no further tool calls, and every model call in it is fitted to its model's token budget before it is sent.

#### Scenario: Plain turn
- **WHEN** the owner writes "I want a bench for the hall"
- **THEN** the reply is text from Intake and nothing is pending

#### Scenario: Round cap
- **WHEN** a specialist would call tools more times than the cap allows
- **THEN** the turn ends with a text reply that says what remains undone

## ADDED Requirements

### Requirement: A thread carries its tool toggles
Each thread SHALL have a tool setting per toggleable plugin, starting from the manifest's default; the owner SHALL be able to read and change them on the thread through an owner-gated route, and a change SHALL apply from the thread's next turn. A pending confirmation SHALL resume with the tools of the turn that raised it.

#### Scenario: Toggles listed
- **WHEN** the owner reads a new thread's tools
- **THEN** each toggleable plugin is listed with its manifest default
