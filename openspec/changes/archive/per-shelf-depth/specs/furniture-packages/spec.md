## ADDED Requirements

### Requirement: A module can state per-shelf depths
A module SHALL accept an optional `shelf_depths_mm` list and an optional `shelf_depth_align`.

- **Depths.** `shelf_depths_mm` holds one entry per shelf, lowest first, counting fixed and adjustable shelves together (the same order as `shelf_positions_mm` and `shelf_kinds`). Each entry is either a whole-millimetre cut depth or `null`. A `null` entry, and every shelf when the field is omitted, SHALL use the module's back-reduced depth (module depth less the back thickness, or the full depth when there is no back).
- **Align.** `shelf_depth_align` is `"back"` or `"front"`. Without `shelf_depths_mm`, the align SHALL be omitted. With depths and no align, the align SHALL be `"back"`.
  - `"back"`: each custom shelf's rear face sits on the carcass inner rear. A depth greater than the back-reduced depth sticks out past the side fronts; a smaller depth recesses from the front.
  - `"front"`: each custom shelf's front face sits on the side fronts. A greater depth sticks out past the carcass rear; a smaller depth leaves a gap at the back.

Each shelf board SHALL be cut and drawn at its own depth and y-placement from that rule. Shelf rows of one kind SHALL be grouped by cut width and cut depth: one (width, depth) keeps `<module>-shelf` or `<module>-adjustable-shelf` with its quantity; several become `<module>-shelf-<n>` or `<module>-adjustable-shelf-<n>`, numbered by first appearance from the lowest level and, within a level, from the left. Dividers, sides, top and bottom SHALL stay at the back-reduced carcass depth.

Without an envelope, the build's overall depth SHALL include any shelf that sticks out past the carcass. When an envelope is set, a shelf that leaves the envelope SHALL be refused. Overlap checks SHALL use each shelf's placed box.

On a folded module, a stated depth greater than the smallest inner depth available along that shelf's thickness SHALL be refused, naming `shelf_depths_mm`.

The document SHALL be refused, naming the field and the problem, when:
- `shelf_depths_mm` is given and the module has no shelves;
- the list length differs from the shelf count;
- an entry is below 50 mm;
- `shelf_depth_align` is given without `shelf_depths_mm`;
- a shelf leaves the envelope;
- a folded module cannot fit the stated depth at that shelf.

`revise_package` SHALL be able to set and clear `shelf_depths_mm` (`[]` clears) and `shelf_depth_align`. Clearing depths SHALL clear the align. A document without either field SHALL derive and be drawn exactly as before.

#### Scenario: One shelf deeper, back-flush
- **WHEN** a module 400 mm deep with an 12 mm back has 4 fixed shelves and `shelf_depths_mm` [null, 500, null, null] with align `"back"`
- **THEN** it is accepted; shelf 2 is cut 500 mm deep with its rear on the inner rear (112 mm past the side fronts); the other three shelves are cut at the back-reduced depth of 388 mm

#### Scenario: Shallower shelf, front-flush
- **WHEN** a module 400 mm deep with no back has 3 shelves, `shelf_depths_mm` [400, 400, 250] and `shelf_depth_align` `"front"`
- **THEN** the top shelf is cut 250 mm deep with its front on the side fronts, and the cut list holds a separate row for that depth

#### Scenario: Wrong list length
- **WHEN** a module with 4 shelves lists three depths
- **THEN** it is refused, naming `modules[0].shelf_depths_mm` and the 4 shelves expected

#### Scenario: Align without depths
- **WHEN** a module carries `shelf_depth_align` `"front"` and no `shelf_depths_mm`
- **THEN** it is refused, naming `shelf_depth_align`

#### Scenario: Protruding shelf grows overall depth
- **WHEN** a document with one 400 mm deep module, no envelope, and one back-flush shelf at 500 mm is derived
- **THEN** `overall.d` is at least 500 mm

#### Scenario: Depths cleared in a revision
- **WHEN** module `cabinet` has custom depths and align, and the Designer revises it with `shelf_depths_mm` []
- **THEN** the proposed version has neither depths nor align, and the change lines name the clear

#### Scenario: Old document unchanged
- **WHEN** a document with neither field is derived and built
- **THEN** its cut list, hardware and shelf boxes equal those of the same document before this change

## MODIFIED Requirements

### Requirement: A module can carry adjustable shelves and name its hardware items
A module SHALL accept:
- a number of adjustable shelves, from 0 to 20, with 0 as the default;
- a shelf-pin item key, used when the module has adjustable shelves.

A door entry SHALL accept a hinge item key. Without one, the door SHALL use `hinge-concealed-110`, as today. An item key SHALL be a hardware key, the same key a price-list entry and a data sheet use.

The cut list SHALL hold one adjustable-shelf row per module that has adjustable shelves (one per bay when the module's bays differ in width, as set out in "A module can carry vertical dividers", and one per distinct depth when per-shelf depths differ, as set out in "A module can state per-shelf depths"). Each board SHALL be cut between the sides (or the bay's sides) at that shelf's depth (the back-reduced depth when no custom depth is set for it), less the adjustable-shelf clearance on the width. The hardware SHALL hold one line per shelf-pin item, with a quantity of pins per shelf times the adjustable shelf boards. Without the pins-per-shelf value, the line SHALL have no quantity, as set out in the hardware-drilling spec. Hinge lines SHALL be keyed by the door's hinge item, and their count per door SHALL be unchanged unless that item's data sheet states its own count table. When a hinge's data sheet names a mounting-plate item, the hardware SHALL hold that plate's line with one plate per hinge.

A built version SHALL draw each adjustable shelf as a board at its height and depth inside its module. When the module states no shelf spacing or positions, the fixed and adjustable shelves SHALL be spaced evenly together. With a spacing or positions, they SHALL be placed as set out in "A module can state its shelf spacing or shelf positions". A module with no adjustable shelves SHALL be drawn exactly as before. No hole, pin, hinge cup or plate SHALL be drawn.

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
