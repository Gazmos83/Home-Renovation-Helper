## ADDED Requirements

### Requirement: A measured room is duplicated with at most one layout version
The owner SHALL be able to make a new room from an existing measured room under a new name. The name SHALL be non-blank and SHALL NOT match another room's name, ignoring case. The copy SHALL take the source room's corners, ceiling height, wall thickness, openings and notes unchanged. The copy SHALL belong to no apartment, even when the source belongs to one, and its corners SHALL stay in the frame they were measured in.

When the source room has a room composition, the owner MAY name one of its versions to copy; with none named, no layout SHALL be copied. A named version SHALL become version 1 of the copy's composition, with the change line "duplicated from <room> v<n>". Its items, their placements, hidden flags, layers, lights and the floor finish SHALL be kept as they are. The copied layout SHALL pass every check a new composition of the copy passes: each placement, each opening, the design rules, and approved piece versions only. Its headless build SHALL start at once, and no render SHALL start.

The application SHALL NOT copy composition approvals, renders, variants, other composition versions, the pieces' room assignment, the pieces' saved places in the room, conversations, or blueprints. The source room and its composition SHALL NOT change. Every refusal SHALL be checked before anything is written, and a refused duplicate SHALL write nothing.

#### Scenario: Room with its latest layout
- **WHEN** `Wohnen` has composition versions 1 to 18, version 18 holds approved pieces, and the owner duplicates `Wohnen` as "Wohnen B" with version 18
- **THEN** the room "Wohnen B" exists with the same corners, height, wall thickness, openings and notes, its composition has version 1 with the items and floor of `Wohnen` v18 and the change line "duplicated from Wohnen v18", and its headless build has started

#### Scenario: Room only
- **WHEN** the owner duplicates `Wohnen` as "Wohnen B" with no layout
- **THEN** "Wohnen B" exists with no composition, and nothing builds

#### Scenario: Name taken
- **WHEN** the owner duplicates `Wohnen` as "küche" and a room `Küche` exists
- **THEN** the duplicate is refused saying a room is already named that, and nothing is written

#### Scenario: Layout with an unapproved piece
- **WHEN** `Wohnen` v18 holds `sideboard-copy` v1, which is no longer approved, and the owner duplicates `Wohnen` with version 18
- **THEN** the duplicate is refused naming `sideboard-copy` v1 as not approved, and no room or composition is created

#### Scenario: Room of an apartment
- **WHEN** the owner duplicates a room that belongs to the apartment `Amesbury`
- **THEN** the copy belongs to no apartment, and the source room still belongs to `Amesbury`

#### Scenario: Source unchanged
- **WHEN** a duplicate of `Wohnen` has been made
- **THEN** `Wohnen`'s measurements, composition versions, approvals, pieces and conversations are as they were
