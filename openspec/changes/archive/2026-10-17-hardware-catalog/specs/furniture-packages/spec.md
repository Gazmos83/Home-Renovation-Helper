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

A built version SHALL draw each adjustable shelf as a board inside its module. When the module states no shelf spacing or positions, the fixed and adjustable shelves SHALL be spaced evenly together. With a spacing or positions, they SHALL be placed as set out in "A module can state its shelf spacing or shelf positions". A module with no adjustable shelves SHALL be drawn exactly as before. No drilled hole SHALL be drawn. Shelf pins, hinge cups, hinge arms and mounting plates SHALL be drawn as set out in "Hardware with an exact position is drawn".

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


#### Scenario: Pins drawn at exact holes
- **WHEN** a module with two adjustable shelves is built and its shelf-pin data sheet gives exact hole positions and 4 pins per shelf
- **THEN** the model holds 8 shelf-pin objects at those holes in the `hardware` layer, and no hole is drawn

## ADDED Requirements

### Requirement: Hardware with an exact position is drawn
A built version SHALL draw every hardware piece whose position the spec and its inputs fix exactly. The pieces come from one shared layout that derive also uses to count them, so the model and the hardware list cannot disagree. Each piece's shape, size and finish SHALL come from its hardware-catalog entry.

The pieces drawn are:
- a hinge (cup, arm and mounting plate) at each exact cup position in the drilling list;
- a shelf pin at each exact pin position;
- a pair of drawer runners for each drawer, of the derived runner length, on the drawer box sides at the box's bottom edge;
- a wall-shelf bracket at each position the owner stated;
- each hanging rail and its supports.

A position the drilling list gives as a range or as a rule in words SHALL NOT be narrowed to draw a piece; that piece is not drawn. Confirmat screws and drilled holes SHALL NOT be drawn. A hand-written hardware line SHALL NOT be drawn unless a hanging rail places it. Handles stay as set out in "A front can carry a modelled handle".

Every drawn piece SHALL be its own object, named `<hardware line id>#<n>` from 1, parented to its module's empty, in a `hardware` layer, carrying its `hardware_key` and no `part_id`. Hardware pieces SHALL NOT appear in the cut list and SHALL NOT change `overall` or the envelope check. Pieces of one line SHALL share one mesh.

Each hardware row in `spec.json` SHALL carry `shown`: the number of its pieces drawn, 0 when none are. A document with no hardware lines and no `hanging_rails` SHALL derive the same cut list and hardware as before. It differs only by `shown` and the `hardware` layer.

#### Scenario: Hinges drawn
- **WHEN** a module with two 700 mm hinged doors is built, and the hinge data sheet gives an exact cup edge distance and positions
- **THEN** the model holds `hinge-concealed-110#1` to `#4` in the `hardware` layer at the drilling list's cup positions, and the hinge row has `shown` 4

#### Scenario: Ranged position not drawn
- **WHEN** a wall shelf's brackets are calculated, so its outer brackets are "100–200 mm from each end"
- **THEN** no bracket is drawn for that shelf, and its bracket row has `shown` 0

#### Scenario: Free line not drawn
- **WHEN** a design lists `wall-anchors` ×10 as a hand-written line
- **THEN** no object is drawn for it, and its row has `shown` 0

#### Scenario: Confirmat never drawn
- **WHEN** any carcass is built
- **THEN** the `confirmat-7x50` row has `shown` 0, and no screw object exists

#### Scenario: Layer switch
- **WHEN** a built version has drawn hardware
- **THEN** its `spec.json` layers name `hardware`, and switching it off in the inspector hides exactly those objects

### Requirement: A module can carry hanging rails
A module SHALL accept `hanging_rails`, at most 4 entries. Each entry gives:
- `bay`: 1-based, default 1;
- `z`: the rail centre in mm above the top of the bottom panel. Required.
- optional `inset_y_mm`: from the front of the sides, default half the inner depth;
- optional `finish`: a catalog finish, default `chrome`;
- optional `key`: the rail item, default `rail-oval-30x15`;
- optional `support_key`: default `rail-support-oval`.

The entry SHALL be refused, naming the field, when:
- the bay does not exist;
- the rail crosses a shelf or divider in its bay;
- the rail's top is closer to the board above than the hook clearance (40 mm, fixed in code, with the rail's 30 mm section);
- the module has `side_folds` (not supported yet).

The hardware SHALL hold:
- one rail line per key and cut length, id `<key>-<cut length>`, the cut length being the bay's inner width less 1 mm at each end (fixed in code), with the item naming it ("Wardrobe rail oval 30×15 mm, cut to 894 mm");
- one support line per support key: two per rail, plus any centre supports the rail-support count rule gives for the rail's length. Without that rule, the note SHALL say no centre-support rule applies.

The rail and its supports SHALL be drawn as set out in "Hardware with an exact position is drawn". `revise_package` SHALL change a module's `hanging_rails` as a whole list, and its change line SHALL describe the rails before and after.

#### Scenario: Rail in a wardrobe bay
- **WHEN** a 932 mm wide module with 18 mm sides carries `hanging_rails: [{"z": 1650}]`
- **THEN** the hardware holds `rail-oval-30x15-894` (cut to 894 mm) and `rail-support-oval` ×2, and the model draws the rail and both supports in the `hardware` layer

#### Scenario: Rail through a shelf refused
- **WHEN** a rail's `z` falls within a shelf's thickness in its bay
- **THEN** it is refused naming `modules[i].hanging_rails[j].z` and the shelf

#### Scenario: Missing height refused
- **WHEN** a rail entry gives no `z`
- **THEN** it is refused naming `z`, and no height is assumed
