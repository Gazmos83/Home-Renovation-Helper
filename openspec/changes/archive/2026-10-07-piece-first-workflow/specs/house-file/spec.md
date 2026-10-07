## MODIFIED Requirements

### Requirement: Pieces and versions mirror the package folders
The house file SHALL record one piece per package id with its name, its confirmed brief and, when known, its room; and one version record per `docs/renders/<id>/v<N>` folder the agents create, carrying the change lines, the version it was revised from, and when it was approved (or nothing). A piece SHALL be recorded only by a confirmed `create_piece`, a version only by a confirmed `create_piece` or `revise_package`; a package the owner created directly through the package routes SHALL still be readable as a piece without a brief. A new version SHALL start unapproved. At most one version of a piece SHALL be approved at a time; approving a version SHALL clear the approval of any other version of that piece. Only the owner's approval route SHALL set or clear approval.

#### Scenario: First version
- **WHEN** the owner confirms a new piece `hall-bench`
- **THEN** the house file holds piece `hall-bench` with its brief and version 1 revised from nothing, unapproved

#### Scenario: Revision
- **WHEN** the owner confirms a revision of `hall-bench` ("cabinet: 2 shelves → 3")
- **THEN** version 2 is recorded as revised from version 1 with that change line, and version 1 is unchanged

#### Scenario: Revision of an approved version starts unapproved
- **WHEN** `hall-bench` version 2 is approved and the owner confirms a revision
- **THEN** version 3 is recorded unapproved and version 2 stays approved

#### Scenario: Approving another version moves the approval
- **WHEN** version 2 is approved and the owner approves version 3
- **THEN** version 3 is approved and version 2 is not

### Requirement: Every turn starts from the house file
Intake and the Designer SHALL be given, at the start of each turn, the rooms (name and size), the preferences, the pieces with their latest version, its status and which version is approved (or that none is), and any open generator-extension requests, and the Designer SHALL also be given the open items of the latest review of the bound piece, as application data clearly labelled as the owner's own and never as an instruction. Owner-authored text in it SHALL be neutralised so it cannot carry the untrusted-content delimiter.

#### Scenario: A second piece starts with the room known
- **WHEN** the living room is recorded and the owner asks for a second piece
- **THEN** the Intake turn's context names the living room's size and the Designer's names the first piece, without the owner repeating them

#### Scenario: Delimiter in a room name
- **WHEN** a stored room name contains the untrusted-content delimiter
- **THEN** the context shows it neutralised

#### Scenario: Review items reach the Designer
- **WHEN** the latest review of the bound piece has two open items
- **THEN** the Designer's context lists both with their aspect, expectation and observation

#### Scenario: Approval reaches the agents
- **WHEN** `listening-wall` version 4 is approved and version 5 exists
- **THEN** the turn's context names version 5 as latest and version 4 as approved
