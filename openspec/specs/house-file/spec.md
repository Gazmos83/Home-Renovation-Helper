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
The house file SHALL record one piece per package id with its name, its confirmed brief and, when known, its room; and one version record per `docs/renders/<id>/v<N>` folder the agents create, carrying the change lines and the version it was revised from. A piece SHALL be recorded only by a confirmed `create_piece`, a version only by a confirmed `create_piece` or `revise_package`; a package the owner created directly through the package routes SHALL still be readable as a piece without a brief.

#### Scenario: First version
- **WHEN** the owner confirms a new piece `hall-bench`
- **THEN** the house file holds piece `hall-bench` with its brief and version 1 revised from nothing

#### Scenario: Revision
- **WHEN** the owner confirms a revision of `hall-bench` ("cabinet: 2 shelves → 3")
- **THEN** version 2 is recorded as revised from version 1 with that change line, and version 1 is unchanged

### Requirement: Generator-extension requests are recorded
When a spec is refused because it names a field the schema does not define, the house file SHALL record a generator-extension request carrying the field name, the owner's words that asked for it, the piece if any and when it happened. The request SHALL be listable so a later OpenSpec change can grow the schema from it.

#### Scenario: Unknown field recorded
- **WHEN** the Designer's document carries `modules[0].bevel_mm` because the owner asked for a bevelled edge
- **THEN** the document is refused naming `bevel_mm`, nothing is built, and a request naming `bevel_mm` with the owner's words is recorded

### Requirement: Threads are indexed
The house file SHALL index every conversation the owner starts with its id, title, the piece it is about when one is bound, when it started and when it last had a turn, so conversations can be listed and reopened. The messages themselves live in the checkpointer.

#### Scenario: Listing
- **WHEN** the owner has started two conversations
- **THEN** both are listed with their titles, newest activity first

### Requirement: Every turn starts from the house file
Intake and the Designer SHALL be given, at the start of each turn, the rooms (name and size), the preferences, the pieces with their latest version and status, and any open generator-extension requests, as application data clearly labelled as the owner's own and never as an instruction. Owner-authored text in it SHALL be neutralised so it cannot carry the untrusted-content delimiter.

#### Scenario: A second piece starts with the room known
- **WHEN** the living room is recorded and the owner asks for a second piece
- **THEN** the Intake turn's context names the living room's size and the Designer's names the first piece, without the owner repeating them

#### Scenario: Delimiter in a room name
- **WHEN** a stored room name contains the untrusted-content delimiter
- **THEN** the context shows it neutralised
