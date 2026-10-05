## MODIFIED Requirements

### Requirement: Every turn starts from the house file
Intake and the Designer SHALL be given, at the start of each turn, the rooms (name and size), the preferences, the pieces with their latest version and status, and any open generator-extension requests, and the Designer SHALL also be given the open items of the latest review of the bound piece, as application data clearly labelled as the owner's own and never as an instruction. Owner-authored text in it SHALL be neutralised so it cannot carry the untrusted-content delimiter.

#### Scenario: A second piece starts with the room known
- **WHEN** the living room is recorded and the owner asks for a second piece
- **THEN** the Intake turn's context names the living room's size and the Designer's names the first piece, without the owner repeating them

#### Scenario: Delimiter in a room name
- **WHEN** a stored room name contains the untrusted-content delimiter
- **THEN** the context shows it neutralised

#### Scenario: Review items reach the Designer
- **WHEN** the latest review of the bound piece has two open items
- **THEN** the Designer's context lists both with their aspect, expectation and observation
