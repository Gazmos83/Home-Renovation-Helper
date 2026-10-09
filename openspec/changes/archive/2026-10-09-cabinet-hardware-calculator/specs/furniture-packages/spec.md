## ADDED Requirements

### Requirement: A module can carry adjustable shelves and name its hardware items
A module SHALL accept:
- a number of adjustable shelves, from 0 to 20, with 0 as the default;
- a shelf-pin item key, used when the module has adjustable shelves.

A door entry SHALL accept a hinge item key. Without one, the door SHALL use `hinge-concealed-110`, as today. An item key SHALL be a hardware key, the same key a price-list entry and a data sheet use.

The cut list SHALL hold one adjustable-shelf row per module that has adjustable shelves. The row SHALL be cut between the sides at the back-reduced depth, less the adjustable-shelf clearance. The hardware SHALL hold one line per shelf-pin item, with a quantity of pins per shelf times the adjustable shelves. Without the pins-per-shelf value, the line SHALL have no quantity, as set out in the hardware-drilling spec. Hinge lines SHALL be keyed by the door's hinge item, and their count per door SHALL be unchanged unless that item's data sheet states its own count table. When a hinge's data sheet names a mounting-plate item, the hardware SHALL hold that plate's line with one plate per hinge.

A built version SHALL draw each adjustable shelf as a board inside its module. The fixed and adjustable shelves SHALL be spaced evenly together. A module with no adjustable shelves SHALL be drawn exactly as before. No hole, pin, hinge cup or plate SHALL be drawn.

A document with no new field SHALL derive the same cut list and hardware as before.

#### Scenario: Adjustable shelves listed
- **WHEN** a 600 mm wide module with 18 mm sides has two adjustable shelves and shelf pin `shelf-pin`, whose data sheet gives 4 pins per shelf
- **THEN** the cut list holds one adjustable-shelf row with quantity 2, and the hardware holds `shelf-pin` with quantity 8

#### Scenario: Default hinge unchanged
- **WHEN** the shipped fold-down-desk template is derived
- **THEN** its cut list and hardware equal those derived before this change, row for row

#### Scenario: Hinge item named
- **WHEN** a door entry names hinge `hinge-blum-clip-110`
- **THEN** its hinges are listed under `hinge-blum-clip-110`, and no `hinge-concealed-110` line is added for that door

#### Scenario: Unknown module field
- **WHEN** a module carries `pin_pitch_mm`
- **THEN** it is refused naming `pin_pitch_mm`, and the refusal becomes a generator-extension request

### Requirement: A custom build can carry wall-hung shelves on brackets
A custom-build document SHALL accept an optional list of wall shelves. Each wall shelf SHALL have:
- an id, unique among the document's wall shelves, modules and extra parts, and a name;
- the position of the board's left end and underside, in mm in the build's frame;
- the board's length, depth and material slot;
- the bracket item key;
- optionally, the owner's bracket positions, in mm from the board's left end to each bracket's centre.

Without the owner's positions, the bracket count and positions SHALL be calculated from the bracket rules:
- the count is the minimum the count rule gives for the board's length;
- the two outer brackets are listed at the spacing rule's end-distance range from each end, as cited, for example "100–200 mm from each end", and never at a value picked inside it;
- any other brackets are listed as "evenly spaced between them", in words, with no number.

With the owner's positions, those positions SHALL be used as an override. They SHALL be judged by the bracket checks, which can only warn.

When a bracket rule is missing, or the board is not longer than twice the shortest end distance, the positions SHALL be blank and the bracket line SHALL have no quantity, with a warning as set out in the hardware-drilling spec.

The document SHALL be refused, naming the field and the problem, when:
- a wall shelf names an undefined material slot;
- an owner's bracket position is not inside the board, or the positions are not strictly increasing;
- the owner's list is given but empty, or holds more than 20 positions;
- a shelf lies outside the envelope.

A field a wall shelf does not define SHALL be refused by name, as for any other part of the document.

The cut list SHALL hold one row per board, with the board's length, depth and material. The hardware SHALL hold one line per bracket item, with a quantity equal to the brackets on every shelf that uses it. The drilling list SHALL give each board's bracket positions and say whether they were calculated or set by the owner.

A built version SHALL draw each board as one object named by the shelf's id, under one empty per shelf. Brackets SHALL NOT be drawn.

`revise_package` SHALL be able to add a wall shelf, remove one, and change a shelf's fields, including setting or clearing its bracket positions. A change naming a shelf the document does not contain SHALL be refused, naming the shelves it does contain.

#### Scenario: Brackets calculated
- **WHEN** a document carries a 1200 mm oak wall shelf, 250 mm deep, with no bracket positions, and the shipped bracket rules apply
- **THEN** it is accepted, the cut list holds one 1200 × 250 mm oak board row, the bracket line has quantity 2, and the drilling list gives two calculated brackets "100–200 mm from each end", with the source, and no single end distance

#### Scenario: Owner's positions kept
- **WHEN** a 1200 mm wall shelf lists brackets at 150, 600 and 1050 mm
- **THEN** the bracket line has quantity 3, the drilling list gives those positions marked as set by the owner, and no bracket warning is shown

#### Scenario: Bracket outside the board
- **WHEN** a 900 mm wall shelf lists a bracket at 950 mm
- **THEN** it is refused, naming `wall_shelves[0].bracket_positions_mm` and the board's length, and no package is created

#### Scenario: Positions out of order
- **WHEN** a wall shelf lists brackets at 600, 150 and 1050 mm
- **THEN** it is refused, naming `wall_shelves[0].bracket_positions_mm` as not strictly increasing

#### Scenario: Unknown wall-shelf field
- **WHEN** a wall shelf carries `load_kg`
- **THEN** it is refused, naming `load_kg`, and the refusal becomes a generator-extension request

#### Scenario: Board drawn, brackets not
- **WHEN** a version with a wall shelf is built headless
- **THEN** the model holds the board object and the shelf's empty, and no bracket object

#### Scenario: Bracket positions set in a revision
- **WHEN** the Designer revises a package, setting a shelf's brackets to 150, 600 and 1050 mm
- **THEN** a new version is proposed with those positions as the owner's override, and its change lines name the shelf and its old and new positions

### Requirement: A build receives its version's hardware inputs and publishes the drilling list
The headless build SHALL receive the version's saved hardware inputs together with its spec. Its emitted `spec.json` SHALL carry `drilling`:
- the drilling list per part;
- the drilling-work counts;
- the warnings;
- whether the list is complete.

Its `cutlist.csv` and `hardware.csv` SHALL equal the derivation from the same spec and inputs, row for row. A build of a version with no saved inputs SHALL run as before.

#### Scenario: Build parity with inputs
- **WHEN** a version with adjustable shelves and saved inputs is built with the pinned Blender
- **THEN** `cutlist.csv` and `hardware.csv` equal the backend's derivation from the same spec and inputs, and `spec.json` `drilling` equals the backend's drilling list
