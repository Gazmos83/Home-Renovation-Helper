## ADDED Requirements

### Requirement: A composition version's room dimensions can be read
The owner SHALL be able to read, for one composition version, the dimensions of its room plan, derived only from that version's stored document, so they never change after the version is made. The read SHALL list every unique wall once, with its surface label as in the surface map (`wall <n>` for a room, `<room>: wall <n>` for an apartment), its two plan end points and its length in millimetres; a wall two rooms of an apartment share SHALL be listed once. It SHALL list each room's ceiling height in millimetres with the room's name and a plan point inside that room. The composition list SHALL name each listed version's dimensions by their composition route when the version has `model.glb`. An unknown composition or version, or a version whose document cannot be read, SHALL answer not found. The read SHALL contain no file-system path.

#### Scenario: Room walls
- **WHEN** the owner reads the dimensions of `Wohnen` v2, whose plan has corners (0,0), (6200,0), (6200,5700), (3500,5700) and (1289,6064) and a 2500 mm ceiling
- **THEN** walls 1 to 5 are listed with lengths 6200, 5700, 2700, 2241 and 6199 mm (rounded to whole millimetres) and one ceiling of 2500 mm for `Wohnen`

#### Scenario: Apartment shared wall and heights
- **WHEN** the owner reads the dimensions of an apartment version where `Bad` and `Flur` share one wall and `Bad` is 2400 mm high while the apartment ceiling is 2550 mm
- **THEN** the shared wall is listed once, `Bad` has a 2400 mm ceiling and every other room 2550 mm

#### Scenario: Unknown version
- **WHEN** the owner reads the dimensions of a version that does not exist
- **THEN** the answer is not found
