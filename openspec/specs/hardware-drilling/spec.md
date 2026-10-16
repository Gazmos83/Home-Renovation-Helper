# hardware-drilling Specification

## Purpose
Defines how a piece version's drilling positions, hardware quantities and drilling-work counts are calculated from its spec and from cited hardware data, and how missing data is shown instead of guessed.

## Requirements

### Requirement: Drilling is calculated by a closed set of cited calculations
A version's drilling list SHALL be calculated by a closed set of calculations. Each calculation SHALL name:
- the hardware kind it reads;
- the input values it needs;
- the source each value came from.

The set SHALL hold three calculations:
- **Shelf pins.** For every module with adjustable shelves, on the inner face of each side: one hole column at the front setback and one at the rear setback. Holes run from the first hole height to the last hole height at the pitch. The list states the hole diameter and depth, and the pins per shelf.
- **Hinges.** For every door: the number of hinges, and each hinge's distance from the door's bottom end. The two outer hinges sit at the end distance from each end, and any others are evenly spaced between them. The list states the cup diameter, the cup depth and the cup edge distance. For every hinge it also lists the mounting plate's height and setback on the side at the door's hinge edge.
- **Wall-shelf brackets.** For every wall shelf: the bracket count and the bracket positions, as set out in the furniture-packages and design-guidelines specs.

Each position SHALL be an exact value, a range, or a rule in words, as set out in "A ranged value stays a range".

The same spec and the same inputs SHALL always give an identical drilling list. A calculation SHALL NOT read the output of another calculation. A new calculation SHALL be added only through its own change, and SHALL NOT change what the existing calculations return.

#### Scenario: Shelf-pin holes listed
- **WHEN** a version has a module with two adjustable shelves, and its shelf-pin data sheet gives every value
- **THEN** the drilling list names the module's side row, gives each column's setback and each hole's height from the side's bottom end, and states the hole diameter, the depth and the source of each value

#### Scenario: Hinge positions listed
- **WHEN** a version has a 1200 mm door, and its hinge data sheet gives every value
- **THEN** the drilling list names the door row and gives three hinge positions, the cup diameter, depth and edge distance, and the plate positions on the side, each with its source

#### Scenario: Same inputs, same list
- **WHEN** the drilling list of one version is calculated twice
- **THEN** both results are identical

### Requirement: A ranged value stays a range
A value its source gives as a range SHALL be stored and listed as that range, with its minimum, maximum, unit and source. It SHALL NOT be narrowed to a midpoint or any other value inside it. A value its source gives as one number SHALL stay exact.

The drilling list SHALL list a position as:
- an exact value, when every value it needs is exact;
- a range, when it needs one ranged value and otherwise exact values only, for example the outer brackets "100–200 mm from each end";
- its rule in words, naming each value, when it depends on where the owner marks inside a range or on two ranged values, for example the inner brackets "evenly spaced between them". No number SHALL be given for it.

A range SHALL NOT count as a missing value: it adds no warning and does not mark the list incomplete. Counts SHALL be whole numbers and SHALL NOT be ranges: pins per shelf, the hinge count table and the bracket count table. Hinges per door, brackets per board, pins and hinge cup borings SHALL be counted as for exact values. An owner's position SHALL still be judged against the range it must lie in, with a warning, as set out in the design-guidelines spec.

#### Scenario: A ranged value is listed as a range
- **WHEN** a 1500 mm wall shelf has no owner positions, and the bracket spacing rule gives ends of 100–200 mm from `topnotch-shelf-brackets`
- **THEN** the drilling list gives 3 brackets: the first and last "100–200 mm from each end", and the middle one "evenly spaced between them", each with the source. No single end distance appears, and the list is not marked incomplete

#### Scenario: A single value stays exact
- **WHEN** a hinge data sheet gives the cup diameter as 35 mm
- **THEN** the drilling list gives "cup Ø 35 mm"

#### Scenario: A ranged first hole
- **WHEN** a shelf-pin data sheet gives the first hole as 50–60 mm and every other value as one number
- **THEN** the side rows give the hole heights as a rule in words naming the range and the pitch, the shelf-pin hole count is left out, and no warning is added

### Requirement: Missing drilling data is shown, never guessed
A position whose input value is missing SHALL be left blank. The drilling list SHALL carry a warning that names the part, the calculation and each missing value, for example "drilling positions missing: cup edge distance". The version's cut list SHALL then be marked incomplete, and SHALL list every warning. A missing value SHALL NOT be guessed, defaulted or taken from another item's data sheet. A hardware quantity that needs a missing value SHALL be listed with no quantity, with a note naming the value. Missing data SHALL NOT refuse the spec, the build or the version.

#### Scenario: Cup edge distance missing
- **WHEN** a version's hinge data sheet has no cup edge distance
- **THEN** the door's hinge heights are listed, its cup edge distance is blank, the warning reads "drilling positions missing: cup edge distance", and the cut list is marked incomplete

#### Scenario: No data sheet at all
- **WHEN** a version's module names a shelf pin that has no data sheet
- **THEN** the side rows list no holes, the warning names the shelf pin as having no data sheet, the shelf-pin hardware line has no quantity, and the version still builds

#### Scenario: Never borrowed
- **WHEN** a version uses two hinges and only one has a data sheet
- **THEN** the doors with the other hinge have blank cup values, and no value from the first data sheet appears on them

### Requirement: A version keeps the inputs it was calculated from
When a version is created, by a create, a revision, a spec edit or a rebuild, the service SHALL save a copy of every input it uses into the version folder:
- each hardware data sheet the spec names;
- the bracket rules.

The copy SHALL carry each data sheet's values, its source and when it was last changed. Every derivation of that version SHALL read its own copy. These derivations are the build, `cut_list`, the inspector, reviews and pricing. Editing a data sheet or a rule later SHALL NOT change an existing version's drilling list. A version made before this change has no copy. It SHALL be derived exactly as before, and its drilling list SHALL say that drilling was not calculated for it.

#### Scenario: Data sheet edited after the version
- **WHEN** the owner changes a hinge's cup edge distance after `hall-cabinet` version 2 was made
- **THEN** version 2's drilling list still shows the old value with its source, and the next version shows the new one

#### Scenario: An old version
- **WHEN** the owner opens the cut list of a version made before this change
- **THEN** its parts and hardware are unchanged, and the drilling list says drilling was not calculated for it

### Requirement: Drilling-work counts are listed for pricing
The drilling list SHALL count the drilling work:
- hinge cup borings: one per hinge, counted even when the hinge's data sheet is missing;
- shelf-pin holes: the number of holes listed, or no count when the holes are blank or given as a rule in words.

The drilling list SHALL NOT add machining words to a cut-list row's notes.

#### Scenario: Borings counted without data
- **WHEN** a version has four doors of 700 mm with no hinge data sheet
- **THEN** the drilling list counts 8 hinge cup borings, and the hinge positions are blank with their warning

### Requirement: Shelf-pin holes are drilled in dividers too
When a module with adjustable shelves has dividers, the shelf-pin calculation SHALL list:
- one entry for the sides, on the inner face, as before;
- one entry for each divider row, on both faces of each divider in that row.

The entries SHALL use the same columns. A divider's hole row SHALL be the data sheet's first hole, last hole and pitch applied to the divider's own length, measured from its bottom end, which sits on the top face of the board it stands on (the bottom panel for a full-height divider, which gives the same holes as before). A divider whose span holds no adjustable shelf SHALL have no shelf-pin entry. Fixing a shelf (stating it fixed in `shelf_kinds`) SHALL NOT change the side boards' hole row; only the pin count follows the adjustable shelves. The shelf-pin hole count SHALL include the holes of every divider face. When the holes are blank or given as a rule in words, no entry SHALL have a count, as before. A module without dividers SHALL give the same entry as before, and a module whose dividers all run full height SHALL give the same entries as before.

#### Scenario: Holes on a divider listed
- **WHEN** a module has one divider and two adjustable shelves, and the shelf-pin data sheet gives every value with 10 hole heights
- **THEN** the drilling list holds the side entry with 40 holes and a divider entry with 40 holes on both faces, each with its source

#### Scenario: No dividers, unchanged
- **WHEN** a module without dividers has adjustable shelves
- **THEN** its shelf-pin entry equals the one given before this change

#### Scenario: Partial divider drills only its span
- **WHEN** a module has a divider from its top fixed shelf to the top panel, and one adjustable shelf above that fixed shelf and one below it
- **THEN** the divider entry lists the hole row from the data sheet's first hole to its last hole along the divider's own length, measured from its bottom end on the fixed shelf's top face

#### Scenario: Divider with no adjustable shelf in its span
- **WHEN** a module's only divider runs between two fixed shelves with no adjustable shelf between them
- **THEN** the drilling list holds no divider shelf-pin entry for it

#### Scenario: Fixing a shelf keeps the side holes
- **WHEN** the top of four adjustable shelves is fixed through `shelf_kinds`
- **THEN** the side entries list the same holes as before, and the shelf-pin quantity counts 3 adjustable shelves

### Requirement: Drilling on a folded side names the split boards
When a module has `side_folds` and adjustable shelves or hinged doors, the drilling list SHALL name the cut-list side-board rows of that module, not `{module}-side`.

Shelf-pin holes SHALL be listed on each side board's inner face:
- an unfolder side: the same columns and hole heights as today, measured from that board's bottom end;
- a folded side along height: holes whose height is below `from_mm` on the lower board, from that board's bottom end; holes at or above `from_mm` on the upper board, from that board's lower end along the slope;
- a folded side along depth: the same split onto the front and back boards, measured from each board's front end.

Hinge cups SHALL stay on the door row, measured from the door's bottom end as today. Each mounting plate SHALL be listed on the side board that holds that hinge's height (lower or upper, or front or back), with a note when that board is the sloped piece.

A module with no `side_folds` SHALL give the same drilling entries as before.

#### Scenario: Pin holes on the split left side
- **WHEN** the 800 × 2000 × 400 mm cabinet has a left height fold from 1100 mm and adjustable shelves, and the shelf-pin data sheet gives every value
- **THEN** the drilling list names `cabinet-side-left-lower`, `cabinet-side-left-upper` and `cabinet-side-right`, and has no `cabinet-side` row

#### Scenario: Hinge plates on the sloped board
- **WHEN** that cabinet has two hinged doors and a left height fold from 1100 mm, and a hinge above 1100 mm
- **THEN** that hinge's mounting plate is listed on `cabinet-side-left-upper` with a note that it sits on the sloped board

#### Scenario: Unfolder module unchanged
- **WHEN** a module with no `side_folds` has adjustable shelves
- **THEN** its shelf-pin entry still names `{module}-side`

### Requirement: The hinge count per door follows the data sheet, then the hinge-count rule
The hinge calculation SHALL count each door's hinges from, in this order:
1. the count table on the hinge item's data sheet, when the sheet has one;
2. otherwise, the hinge-count rule in the version's frozen inputs;
3. otherwise, the built-in fallback: 2 hinges up to 900 mm, 3 up to 1600 mm, 4 above.

The hinge positions, the plate positions and the hinge cup borings SHALL all use that same count. The count's source SHALL be listed with the hinge entry: the data sheet, the rule's id and its quoted source, or the fallback. The rule SHALL be read only from the frozen inputs, so an existing version's drilling list SHALL NOT change when the rules are edited later. The shelf-pin hole calculation SHALL be unchanged by the pin-count rule: its holes still need the pin item's data sheet.

#### Scenario: Rule decides a 1000 mm door
- **WHEN** a version has two 1000 mm doors, its frozen inputs hold the `hinge-count` rule, and its hinge has no data sheet
- **THEN** the drilling list counts 2 hinges per door and 4 hinge cup borings, and names `hinge-count` and its owner note as the count's source

#### Scenario: Data sheet table wins over the rule
- **WHEN** a hinge's data sheet gives a count table with 3 hinges up to 1100 mm, and a 1000 mm door uses it under the `hinge-count` rule
- **THEN** the door gets 3 hinges, and the source named is the data sheet

#### Scenario: Version without the rule keeps the fallback
- **WHEN** a version's frozen inputs hold no hinge-count rule, and it has a 1000 mm door
- **THEN** the door gets 3 hinges, as before this change

#### Scenario: Frozen rule kept after an edit
- **WHEN** the developer edits `hinge-count` after `hall-cabinet` version 2 was built
- **THEN** version 2's drilling list and hardware are unchanged, and the next version built uses the edited rule
