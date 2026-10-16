## MODIFIED Requirements

### Requirement: A module can carry adjustable shelves and name its hardware items
A module SHALL accept:
- a number of adjustable shelves, from 0 to 20, with 0 as the default;
- a shelf-pin item key, used when the module has adjustable shelves.

A door entry SHALL accept a hinge item key. Without one, the door SHALL use `hinge-concealed-110`, as today. An item key SHALL be a hardware key, the same key a price-list entry and a data sheet use.

The cut list SHALL hold one adjustable-shelf row per module that has adjustable shelves (one per bay when the module's bays differ in width, as set out in "A module can carry vertical dividers"). The row SHALL be cut between the sides (or the bay's sides) at the back-reduced depth, less the adjustable-shelf clearance. The hardware SHALL hold one line per shelf-pin item. Its quantity SHALL be the sum over that item's adjustable shelf boards of each board's pins per shelf, taken from, in this order:
1. the pins per shelf on the item's data sheet;
2. otherwise, the shelf-pin count rule in the inputs, applied to the board's cut width;
3. with neither, the line SHALL have no quantity, as set out in the hardware-drilling spec.

The line's note SHALL name where the count came from: the data sheet, or the rule's id and its source. Hinge lines SHALL be keyed by the door's hinge item. Their count per door SHALL be decided as set out in the hardware-drilling spec: the item's data-sheet count table, else the hinge-count rule in the inputs, else the built-in fallback. Their note SHALL name which of the three decided. When a hinge's data sheet names a mounting-plate item, the hardware SHALL hold that plate's line with one plate per hinge.

A built version SHALL draw each adjustable shelf as a board inside its module. When the module states no shelf spacing or positions, the fixed and adjustable shelves SHALL be spaced evenly together. With a spacing or positions, they SHALL be placed as set out in "A module can state its shelf spacing or shelf positions". A module with no adjustable shelves SHALL be drawn exactly as before. No hole, pin, hinge cup or plate SHALL be drawn.

A document with no new field SHALL derive the same cut list and hardware as before. A derivation without inputs (no data sheets and no rules) SHALL give the same hardware as before this change.

#### Scenario: Adjustable shelves listed
- **WHEN** a 600 mm wide module with 18 mm sides has two adjustable shelves and shelf pin `shelf-pin`, whose data sheet gives 4 pins per shelf
- **THEN** the cut list holds one adjustable-shelf row with quantity 2, and the hardware holds `shelf-pin` with quantity 8

#### Scenario: Pin count from the rule
- **WHEN** the 800 mm wide Kommode module with 18 mm sides has two adjustable shelves (762 mm boards), `shelf-pin` has no data sheet, and the inputs hold the `shelf-pin-count` rule
- **THEN** the hardware holds `shelf-pin` with quantity 8 and a note naming `shelf-pin-count` and its owner note

#### Scenario: Wide shelf takes the beyond count
- **WHEN** a module's adjustable shelf is cut 1162 mm wide, `shelf-pin` has no data sheet, and the inputs hold the `shelf-pin-count` rule
- **THEN** that board counts 5 pins

#### Scenario: Data sheet wins over the pin rule
- **WHEN** `shelf-pin`'s data sheet gives 6 pins per shelf, and the inputs also hold the `shelf-pin-count` rule
- **THEN** each adjustable shelf counts 6 pins, and the note names the data sheet

#### Scenario: No sheet and no rule
- **WHEN** a module has adjustable shelves, and its inputs hold neither a shelf-pin data sheet nor a pin-count rule
- **THEN** the shelf-pin line has no quantity, as before this change

#### Scenario: Hinge count from the rule
- **WHEN** a module has two 1550 mm hinged doors without a hinge data sheet, and the inputs hold the `hinge-count` rule
- **THEN** the hinge line counts 8 hinges and its note names `hinge-count` and its owner note

#### Scenario: Default hinge unchanged
- **WHEN** the shipped fold-down-desk template is derived
- **THEN** its cut list and hardware equal those derived before this change, row for row

#### Scenario: Hinge item named
- **WHEN** a door entry names hinge `hinge-blum-clip-110`
- **THEN** its hinges are listed under `hinge-blum-clip-110`, and no `hinge-concealed-110` line is added for that door

#### Scenario: Unknown module field
- **WHEN** a module carries `pin_pitch_mm`
- **THEN** it is refused naming `pin_pitch_mm`, and the refusal becomes a generator-extension request
