## ADDED Requirements

### Requirement: Hardware items carry cited drilling data
The owner SHALL be able to create, edit and delete one data sheet per hardware item. Each data sheet SHALL have:
- the item's hardware key, unique among data sheets;
- its kind, `hinge` or `shelf_pin`;
- the maker and the model;
- the drilling values its kind takes, each optional and in mm unless it is a count. A measured value SHALL be either one number or a range with a minimum below its maximum, as its source gives it. A count SHALL be one whole number;
- a source.

A `hinge` sheet SHALL take:
- the cup diameter, the cup depth and the cup edge distance;
- the end distance from the door's ends;
- an optional count table of door heights and hinges;
- the mounting-plate item key, the plate setback and the plate hole spacing.

A `shelf_pin` sheet SHALL take:
- the hole diameter and the hole depth;
- the pitch;
- the first and last hole heights;
- the front and rear setbacks;
- the pins per shelf.

The source SHALL be one of two kinds:
- `toom`: the toom product page URL, and optionally the maker's data-sheet URL linked from it. A page URL off the toom host SHALL be refused naming the host.
- `manual`: for an item bought elsewhere, a citation of the item's own data sheet entered by hand, such as the document, page and date.

A data sheet SHALL be refused when it cites a URL or citation another data sheet already cites and its maker or model differs. A value SHALL NOT be accepted without its source. Prices SHALL stay in the price list: an item bought elsewhere is priced by a `manual` price-list entry under the same key. Data sheets SHALL be added to the corpus as `guideline` passages naming the item and its source, and SHALL be removed from it when deleted. No data-sheet value SHALL be shipped in the repository.

A range whose minimum is not below its maximum, or a range given for a count, SHALL be refused naming the value.

#### Scenario: Ranged value kept
- **WHEN** the owner enters a hinge's end distance as 80–120 mm from its cited data sheet
- **THEN** the data sheet holds the range with its source, and the value is never stored as one number

#### Scenario: Range on a count
- **WHEN** the owner enters pins per shelf as 4–6
- **THEN** the data sheet is refused naming pins per shelf as a count

#### Scenario: toom hinge data sheet
- **WHEN** the owner adds a data sheet for `hinge-concealed-110` with its cup values, citing its toom product page
- **THEN** the data sheet exists with its source, and `search_guidelines` can return it with that citation

#### Scenario: Item bought elsewhere
- **WHEN** the owner adds a `manual` data sheet for a shelf pin bought at another shop, citing the maker's leaflet and page
- **THEN** the data sheet exists with that citation, and pricing that pin needs a `manual` price-list entry under the same key

#### Scenario: Another item's data sheet
- **WHEN** the owner cites the toom data sheet of one maker's hinge for a hinge of another model
- **THEN** the data sheet is refused, naming the maker and model the source belongs to

#### Scenario: Page off toom
- **WHEN** a `toom` source names a page on another host
- **THEN** the data sheet is refused naming the host

### Requirement: Wall-shelf brackets are checked for count and spacing
The closed set of piece checks SHALL include a bracket-count check and a bracket-spacing check for every wall shelf in a custom build. Both SHALL be applied by the Designer's create and revise previews like any other piece rule, at the severity their rule states. The same two rules SHALL also give the bracket calculator its count and its end-distance range, which the rule SHALL hold as a range with its minimum, maximum, unit and source.

**Count check.** The count check SHALL read a table of rows, each giving a longest board length and a minimum number of brackets. A board SHALL be judged against the first row whose length is at least the board's length. A board longer than the last row SHALL use the last row. A breach SHALL be fewer brackets than that row's minimum.

**Spacing check.** The spacing check SHALL take:
- the shortest and longest distance from each end of the board to its outer bracket;
- a tolerance for even spacing.

A breach SHALL be either of these:
- an outer bracket closer to its end than the shortest distance, or further from it than the longest;
- with three or more brackets, a gap between neighbouring brackets that differs from the mean gap by more than the tolerance.

A shelf with a single bracket SHALL be judged on its end distances only.

**Reporting.** Each breach SHALL name the rule, the shelf, the measured value, the limit and the source, as for any other rule. Calculated brackets SHALL be judged by the count check. The spacing check SHALL judge the owner's positions only, since calculated positions are the cited range itself.

The shipped rules SHALL hold both checks at severity `warn`, citing the guideline source `topnotch-shelf-brackets`, with every limit quoted from it:
- the count table: up to 600 mm, 2; up to 1200 mm, 2; up to 1800 mm, 3; up to 2000 mm, 4;
- outer brackets 100 to 200 mm from each end;
- inner brackets "at equal distances between the two outer brackets".

#### Scenario: Too few brackets for a long shelf
- **WHEN** a 1500 mm wall shelf's owner positions hold two brackets
- **THEN** the preview shows a warning naming the count rule, the shelf, "2 brackets", "at least 3" and the source

#### Scenario: Length between two rows uses the next row
- **WHEN** a 650 mm wall shelf's owner positions hold two brackets
- **THEN** no count warning is shown, since the 1200 mm row asks for at least 2

#### Scenario: Longer than the table
- **WHEN** a 2400 mm wall shelf's owner positions hold three brackets
- **THEN** the preview warns that the last row asks for at least 4

#### Scenario: Outer bracket too close to the end
- **WHEN** a 1200 mm wall shelf's owner positions are 50, 600 and 1150 mm
- **THEN** the preview warns, for each end, that the outer bracket is 50 mm from it, against a limit of 100 to 200 mm

#### Scenario: Uneven inner spacing
- **WHEN** an 1800 mm wall shelf's owner positions are 150, 500 and 1650 mm
- **THEN** the preview warns that the gaps are not evenly spaced, naming the largest difference from the mean gap and the tolerance

#### Scenario: A warning does not block
- **WHEN** a create preview carries only bracket warnings
- **THEN** the owner can still confirm, and the piece is created with the warnings shown in its summary

#### Scenario: Calculated brackets pass
- **WHEN** a 1500 mm wall shelf has no owner positions
- **THEN** the calculator lists 3 brackets, the outer two at the cited 100–200 mm from each end, and the preview shows no bracket warning

## MODIFIED Requirements

### Requirement: Guidelines are searched and cited
`search_guidelines` SHALL return the matching guideline passages with their publication, note or hardware data sheet, section and date, wrapped as untrusted content, and SHALL say when nothing matched; an agent quoting a guideline SHALL name its source. The Designer and the Researcher SHALL have the tool. The Researcher SHALL use it for a design rule or a number from a guideline, a note or a data sheet, name the publication, note or data sheet and its section, and say it found no guideline rather than quote a rule from memory.

#### Scenario: Ceiling height asked
- **WHEN** the owner asks the Designer what ceiling height a room needs in Berlin
- **THEN** the reply cites the Bauordnung Berlin passage it used, or says it found none

#### Scenario: Researcher asked for a shelf rule
- **WHEN** the owner asks the Researcher how many brackets a 1500 mm shelf needs
- **THEN** the Researcher calls `search_guidelines` and its reply names `topnotch-shelf-brackets` and the section it used, or says it found no guideline

### Requirement: Hard design rules are applied in code
A checked-in design-rules table SHALL hold each rule's id, what it applies to (a placement in a room, or a piece), the measurement checked, its limit and unit, its severity (`warn` or `refuse`) and its source citation; a rule without a citation SHALL fail startup naming the rule. `room_fit` SHALL apply placement rules (for example the clear passage in front of a piece and a door's swing area) and the Designer's create and revise previews SHALL apply piece rules (for example a worktop height range, a shelf span for a board thickness, or a wall shelf's bracket count and spacing). The shelf span SHALL be checked for fixed and adjustable shelves alike. A `warn` breach SHALL appear in the result and the confirmation summary naming the rule, the measured value, the limit and the source; a `refuse` breach SHALL refuse the action the same way. A rule's limit SHALL be quoted from its cited source. More than one rule naming the same bracket check SHALL fail startup naming both rules.

#### Scenario: Passage too narrow
- **WHEN** a wardrobe placed in a room leaves less clear passage in front of it than the placement rule's limit
- **THEN** `room_fit` returns the placement with a warning naming the rule, the measured passage, the limit and its source

#### Scenario: Rule without a source
- **WHEN** the rules table carries a rule with no citation
- **THEN** startup fails naming the rule id

#### Scenario: Adjustable shelves judged for span
- **WHEN** a module with only adjustable shelves is wider than the span rule allows for its board thickness
- **THEN** the preview warns naming the span rule, the measured span, the limit and the source
