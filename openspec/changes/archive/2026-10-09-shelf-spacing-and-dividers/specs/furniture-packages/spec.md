## ADDED Requirements

### Requirement: A module can state its shelf spacing or shelf positions
A module SHALL accept two optional fields. A module MAY state one of them, never both.
- **Shelf spacing.** `shelf_spacing_mm` is a whole number of millimetres: the clear gap between boards. The first shelf's underside SHALL sit one gap above the top face of the bottom panel. Each next shelf's underside SHALL sit one gap plus one board thickness above the previous one.
- **Shelf positions.** `shelf_positions_mm` is a list of whole millimetres: the height of each shelf's underside above the top face of the bottom panel, lowest first. It SHALL hold one entry per shelf, counting fixed and adjustable shelves together.

Shelves SHALL be placed from the bottom up, fixed shelves first, then adjustable shelves, as with even spacing. The board thickness is the carcass slot's thickness. Without either field, shelves SHALL be spaced evenly as before.

The document SHALL be refused, naming the field and the problem, when:
- both fields are given;
- either field is given and the module has no shelves;
- the positions list does not have one entry per shelf;
- the positions are not increasing by at least one board thickness;
- a shelf's top face would be above the underside of the top panel, with the inner height named.

A built version SHALL draw each shelf at its calculated height. The cut list and hardware SHALL be the same as with even spacing; only the heights change. `revise_package` SHALL be able to set and clear either field. Setting one SHALL remove the other, and the change lines SHALL name both.

#### Scenario: Four shelves 355 mm apart
- **WHEN** a module 1600 mm high with 18 mm carcass has 4 fixed shelves and `shelf_spacing_mm` 355
- **THEN** it is accepted, and the shelves' undersides are 355, 728, 1101 and 1474 mm above the top face of the bottom panel

#### Scenario: Spacing too large
- **WHEN** a module 1200 mm high with 18 mm carcass has 4 shelves and `shelf_spacing_mm` 355
- **THEN** it is refused, naming `modules[0].shelf_spacing_mm` and the inner height of 1164 mm, and no package is created

#### Scenario: Uneven positions
- **WHEN** a module with 3 shelves lists `shelf_positions_mm` 300, 700 and 1300
- **THEN** it is accepted, and the shelves are drawn at those heights

#### Scenario: Wrong number of positions
- **WHEN** a module with 3 shelves lists two positions
- **THEN** it is refused, naming `modules[0].shelf_positions_mm` and the 3 shelves expected

#### Scenario: Spacing and positions together
- **WHEN** a module gives both `shelf_spacing_mm` and `shelf_positions_mm`
- **THEN** it is refused, naming both fields

#### Scenario: Spacing set in a revision
- **WHEN** module `cabinet` has 4 shelves at stated positions, and the Designer revises it with `shelf_spacing_mm` 355
- **THEN** the proposed version has the spacing and no positions, and the change lines name both

#### Scenario: Old document unchanged
- **WHEN** a document with neither field is derived and built
- **THEN** its cut list, hardware and shelf heights equal those of the same document before this change

### Requirement: A module can carry vertical dividers
A module SHALL accept `dividers`, a count from 0 to 10, with 0 as the default. It SHALL also accept an optional `divider_positions_mm`: the distance from the inner face of the left side to each divider's left face, in whole millimetres, lowest first, one entry per divider.

A divider SHALL:
- run between the bottom panel and the top panel;
- be cut in the carcass slot's material and thickness, at the back-reduced depth;
- be drawn as its own object in the `carcass` layer.

Without positions, the dividers SHALL split the inner width into equal bays; the bay width is rounded down to a whole millimetre.

The dividers split the module into bays. Shelves SHALL be placed in every bay at the same heights: one shelf level gives one board per bay. Fixed shelves SHALL be cut to the bay's width. Adjustable shelves SHALL be cut to the bay's width less the adjustable-shelf clearance. When every bay has the same width, each shelf kind SHALL keep its one row (`<module>-shelf`, `<module>-adjustable-shelf`) with its quantity multiplied by the bays. When the bays differ, each bay SHALL have its own rows, named with `-bay-<n>` counted from the left.

The cut list SHALL hold one divider row per module (`<module>-divider`). The confirmat screws SHALL be 8 per carcass, plus 4 per fixed shelf board, plus 4 per divider. Shelf pins SHALL be the pins per shelf times the adjustable shelf boards.

The document SHALL be refused, naming the field and the problem, when:
- positions are given and their number differs from `dividers`;
- positions are given without dividers;
- positions are not increasing by more than one board thickness;
- a divider lies outside the inner width;
- any bay would be 0 mm wide or less.

A module without dividers SHALL derive and be drawn exactly as before. `revise_package` SHALL be able to set the count and set or clear the positions.

#### Scenario: Two dividers, equal bays
- **WHEN** a module 1000 mm wide with 18 mm carcass has 2 dividers and 3 fixed shelves
- **THEN** the cut list holds one divider row with quantity 2, and one fixed-shelf row 309 mm long with quantity 9; the confirmat line is 8 + 4 × 9 + 4 × 2 = 52

#### Scenario: Positioned divider, unequal bays
- **WHEN** a module 1000 mm wide with 18 mm carcass has 1 divider at 400 mm and 2 fixed shelves
- **THEN** the cut list holds `<module>-shelf-bay-1` 400 mm long with quantity 2 and `<module>-shelf-bay-2` 546 mm long with quantity 2

#### Scenario: Shelves split by dividers in the model
- **WHEN** a version with 2 dividers and 3 shelves 355 mm apart is built headless
- **THEN** the model holds two divider objects and nine shelf objects, and every shelf's underside is at its calculated height

#### Scenario: Divider outside the module
- **WHEN** a module with 964 mm inner width lists a divider at 960 mm
- **THEN** it is refused, naming `modules[0].divider_positions_mm` and the inner width

#### Scenario: Unknown divider field
- **WHEN** a module carries `divider_material`
- **THEN** it is refused, naming `divider_material`, and the refusal becomes a generator-extension request

## MODIFIED Requirements

### Requirement: A module can carry adjustable shelves and name its hardware items
A module SHALL accept:
- a number of adjustable shelves, from 0 to 20, with 0 as the default;
- a shelf-pin item key, used when the module has adjustable shelves.

A door entry SHALL accept a hinge item key. Without one, the door SHALL use `hinge-concealed-110`, as today. An item key SHALL be a hardware key, the same key a price-list entry and a data sheet use.

The cut list SHALL hold one adjustable-shelf row per module that has adjustable shelves (one per bay when the module's bays differ in width, as set out in "A module can carry vertical dividers"). The row SHALL be cut between the sides (or the bay's sides) at the back-reduced depth, less the adjustable-shelf clearance. The hardware SHALL hold one line per shelf-pin item, with a quantity of pins per shelf times the adjustable shelf boards. Without the pins-per-shelf value, the line SHALL have no quantity, as set out in the hardware-drilling spec. Hinge lines SHALL be keyed by the door's hinge item, and their count per door SHALL be unchanged unless that item's data sheet states its own count table. When a hinge's data sheet names a mounting-plate item, the hardware SHALL hold that plate's line with one plate per hinge.

A built version SHALL draw each adjustable shelf as a board inside its module. When the module states no shelf spacing or positions, the fixed and adjustable shelves SHALL be spaced evenly together. With a spacing or positions, they SHALL be placed as set out in "A module can state its shelf spacing or shelf positions". A module with no adjustable shelves SHALL be drawn exactly as before. No hole, pin, hinge cup or plate SHALL be drawn.

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
