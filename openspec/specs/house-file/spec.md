# house-file Specification

## Purpose
Defines the owner's long-term memory: the measured rooms, style preferences, the pieces designed with their versions, the generator-extension requests the ladder produces, and the index of conversations — what every agent reads first and what only a confirmed action may write.

## Requirements

### Requirement: Rooms are recorded with their measurements
The house file SHALL hold each room by name with its polygon (corners in millimetres, three to twelve, normalised counter-clockwise, forming a simple polygon — convex or not), ceiling height, wall thickness and openings (wall, type door or window, offset, width, height, sill), and optionally the apartment it belongs to, in whose plan frame its corners then lie. A room SHALL be validated like a room-scene document before it is stored: a self-intersecting outline, a repeated corner, an edge shorter than 50 mm, an opening off its wall or above the ceiling, or a door with a sill is refused naming the problem. A room name SHALL be unique.

#### Scenario: A room is stored
- **WHEN** Intake's confirmed numbers describe the living room as a 4000 × 3500 mm rectangle, 2600 mm high, with one door on wall 1
- **THEN** the house file holds that room and a later turn can read it by name

#### Scenario: An L-shaped room is stored
- **WHEN** a room is described by six corners forming an L
- **THEN** the house file holds it with its six corners counter-clockwise

#### Scenario: An impossible room is refused
- **WHEN** a room is submitted whose door carries a sill
- **THEN** it is refused naming the opening and nothing is stored

#### Scenario: A self-intersecting outline is refused
- **WHEN** a room's corners cross themselves (a bow-tie)
- **THEN** it is refused naming the outline and nothing is stored

### Requirement: Preferences are recorded as named values
The house file SHALL hold the owner's style and default preferences as named values (for example `style`, `default_material`, `budget_eur`) that a confirmed Intake step writes and every turn reads.

#### Scenario: Style confirmed
- **WHEN** the owner confirms "light oak, no visible hardware" as the style
- **THEN** `style` reads that text in the next turn's context

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

### Requirement: Generator-extension requests are recorded
When a spec is refused because it names a field the schema does not define, the house file SHALL record a generator-extension request carrying the field name, the owner's words that asked for it, the piece if any and when it happened. The request SHALL be listable so a later OpenSpec change can grow the schema from it.

#### Scenario: Unknown field recorded
- **WHEN** the Designer's document carries `modules[0].bevel_mm` because the owner asked for a bevelled edge
- **THEN** the document is refused naming `bevel_mm`, nothing is built, and a request naming `bevel_mm` with the owner's words is recorded

### Requirement: Threads are indexed
The house file SHALL index every conversation the owner starts with its id, title, the piece it is about when one is bound, when it started and when it last had a turn, so conversations can be listed and reopened. A thread's piece is the one it was started with until a confirmed action creates or revises a piece in it, after which it is that piece. The messages themselves live in the checkpointer.

#### Scenario: Listing
- **WHEN** the owner has started two conversations
- **THEN** both are listed with their titles, newest activity first

#### Scenario: Bound by the action
- **WHEN** a piece is confirmed on a thread that was started without one
- **THEN** the thread's index entry names that piece from then on

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

### Requirement: Compositions are indexed and reach the turn
The house file SHALL record one composition per scope, by scope type and name. It SHALL record one version record per composition version folder, carrying what changed and the version it was revised from. A version SHALL be recorded only by a confirmed `compose_room`.

At the start of each turn, the Designer's and Builder's house note SHALL list each composition's scope, its latest version and build status, and its items by name. Any placed piece version that is no longer approved SHALL be marked as such. Item names come from the owner, so they SHALL be neutralised like other owner text.

#### Scenario: Recorded on yes
- **WHEN** the owner confirms `Wohnen` v1
- **THEN** the house file holds composition `Wohnen` (scope room) with version 1, revised from nothing

#### Scenario: House note marks unapproved
- **WHEN** a placed version has been unapproved
- **THEN** the next Designer turn's house note lists that item marked "no longer approved"
