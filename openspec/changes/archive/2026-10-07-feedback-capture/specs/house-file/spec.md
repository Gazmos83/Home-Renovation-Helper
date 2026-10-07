## MODIFIED Requirements

### Requirement: Every turn starts from the house file
At the start of each turn, Intake and the Designer SHALL be given the rooms (name and size), the preferences, the pieces with their latest version and status, and any open generator-extension requests. The Designer SHALL also be given:
- the open items of the latest review of the bound piece;
- the latest five render ratings on the bound piece, newest first, each with its version, render, tier, rating and comment.

Lighting & materials SHALL be given the same render ratings. All of this SHALL be presented as application data clearly labelled as the owner's own, never as an instruction. Owner-authored text in it SHALL be neutralised so it cannot carry the untrusted-content delimiter.

#### Scenario: A second piece starts with the room known
- **WHEN** the living room is recorded and the owner asks for a second piece
- **THEN** the Intake turn's context names the living room's size and the Designer's names the first piece, without the owner repeating them

#### Scenario: Delimiter in a room name
- **WHEN** a stored room name contains the untrusted-content delimiter
- **THEN** the context shows it neutralised

#### Scenario: Review items reach the Designer
- **WHEN** the latest review of the bound piece has two open items
- **THEN** the Designer's context lists both with their aspect, expectation and observation

#### Scenario: Render feedback reaches the Designer
- **WHEN** the bound piece's v2 `draft` turntable was rated down with "doors look too thick"
- **THEN** the Designer's context lists v2, turntable, `draft`, down and that comment

#### Scenario: Delimiter in a feedback comment
- **WHEN** a feedback comment contains the untrusted-content delimiter
- **THEN** the Designer's and Lighting's context shows it neutralised
