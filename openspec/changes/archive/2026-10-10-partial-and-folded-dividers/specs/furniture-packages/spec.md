## MODIFIED Requirements

### Requirement: A module can carry vertical dividers
A module SHALL accept `dividers`, a count from 0 to 10, with 0 as the default. It SHALL also accept an optional `divider_positions_mm`: the distance from the inner face of the left side to each divider's left face, in whole millimetres, lowest first, one entry per divider. On a module with a side fold, that distance SHALL be measured from the unbent left side's inner face (the carcass thickness from the module's left face).

A module SHALL also accept an optional `divider_spans`: one entry per divider, left to right, each with:
- `from_board`: `"bottom"` or a shelf number from 1, counting every shelf (fixed and adjustable) from the lowest, the board the divider stands on;
- `to_board`: `"top"` or a shelf number, the board the divider reaches.

A shelf named by a span SHALL be a fixed shelf: an adjustable shelf cannot anchor a divider.

Without `divider_spans`, every divider SHALL run between the bottom panel and the top panel. A divider's length SHALL be the clear gap between the top face of its `from_board` and the underside of its `to_board`, rounded down to a whole millimetre.

A divider SHALL:
- run between its two boards;
- be cut in the carcass slot's material and thickness, at the back-reduced depth;
- be drawn as its own object in the `carcass` layer.

Without positions, the dividers SHALL split the inner width into equal bays; the bay width is rounded down to a whole millimetre. On a module with a side fold, they SHALL instead split into equal bays the narrowest inner opening found along their spans and the full back-reduced depth.

A shelf board (fixed or adjustable) SHALL be split into bays only by the dividers whose span crosses that shelf's height; a divider's own `from_board` and `to_board` are not split by it. Fixed shelves SHALL be cut to the bay's width. Adjustable shelves SHALL be cut to the bay's width less the adjustable-shelf clearance. On a folded module, a board or bay segment next to a folded side SHALL be cut to the smallest width along that board's thickness and depth, rounded down to a whole millimetre.

Cut-list rows:
- with full-height dividers on a module without a fold, as before: when every bay has the same width, each shelf kind keeps its one row (`<module>-shelf`, `<module>-adjustable-shelf`) with its quantity multiplied by the bays; when the bays differ, each bay has its own rows, named with `-bay-<n>` counted from the left;
- otherwise the shelf boards of one kind SHALL be grouped by cut width: one width keeps `<module>-shelf` or `<module>-adjustable-shelf` with its quantity; several widths become `<module>-shelf-<n>` or `<module>-adjustable-shelf-<n>`, numbered by first appearance from the lowest level and, within a level, from the left, each with notes naming the shelf levels and bays it covers;
- the dividers SHALL be one `<module>-divider` row while they share a length, else one `<module>-divider-<n>` row per length, numbered from the left.

The confirmat screws SHALL be 8 per carcass, plus 4 per fold joint, plus 4 per fixed shelf board, plus 4 per divider. Shelf pins SHALL be the pins per shelf times the adjustable shelf boards.

The document SHALL be refused, naming the field and the problem, when:
- positions are given and their number differs from `dividers`;
- positions are given without dividers;
- positions are not increasing by more than one board thickness;
- a divider lies outside the inner width;
- any bay would be 0 mm wide or less;
- `divider_spans` is given and its number differs from `dividers`, or it is given without dividers;
- a span names a shelf number the module does not have;
- a span names an adjustable shelf, naming that shelf number and that only fixed shelves can anchor a divider;
- a span's `from_board` is not below its `to_board`;
- on a folded module, a divider would cut into a folded side, or leave a bay 0 mm wide or less, anywhere along its span.

A module without dividers, and a module without a fold whose dividers have no `divider_spans`, SHALL derive and be drawn exactly as before. `revise_package` SHALL be able to set the count, set or clear the positions, and set or clear the spans; `[]` SHALL clear `divider_spans` back to full height, and setting `dividers` to 0 SHALL clear the spans as well.

#### Scenario: Two dividers, equal bays
- **WHEN** a module 1000 mm wide with 18 mm carcass has 2 dividers and 3 fixed shelves
- **THEN** the cut list holds one divider row with quantity 2, and one fixed-shelf row 309 mm long with quantity 9; the confirmat line is 8 + 4 × 9 + 4 × 2 = 52

#### Scenario: Positioned divider, unequal bays
- **WHEN** a module 1000 mm wide with 18 mm carcass has 1 divider at 400 mm and 2 fixed shelves
- **THEN** the cut list holds `<module>-shelf-bay-1` 400 mm long with quantity 2 and `<module>-shelf-bay-2` 546 mm long with quantity 2

#### Scenario: Shelves split by dividers in the model
- **WHEN** a version with 2 dividers and 3 shelves 355 mm apart is built headless
- **THEN** the model holds two divider objects and nine shelf objects, and every shelf's underside is at its calculated height

#### Scenario: Divider from the top shelf to the top
- **WHEN** module `cabinet` is 800 × 2000 × 400 mm with 18 mm carcass, 12 mm back, 4 fixed shelves, 1 divider and `divider_spans` [{`from_board`: 4, `to_board`: "top"}]
- **THEN** it is accepted, the cut list holds `cabinet-divider` 383 × 388 mm with quantity 1 and `cabinet-shelf` 764 mm long with quantity 4, and the confirmat line is 8 + 4 × 4 + 4 = 28

#### Scenario: Divider crosses only the shelf below it
- **WHEN** a module 1000 × 1200 mm with 18 mm carcass has 3 fixed shelves, 1 divider at 400 mm and `divider_spans` [{`from_board`: "bottom", `to_board`: 2}]
- **THEN** the cut list holds `<module>-divider` 573 mm long, `<module>-shelf-1` 400 mm with quantity 1, `<module>-shelf-2` 546 mm with quantity 1 and `<module>-shelf-3` 964 mm with quantity 2, and the confirmat line is 8 + 4 × 4 + 4 = 28

#### Scenario: Partial divider drawn in the model
- **WHEN** the `cabinet` with the divider from shelf 4 to the top is built headless
- **THEN** the model holds one divider object whose bottom face meets the top face of the fourth shelf and whose top face meets the underside of the top panel, and four whole shelf objects

#### Scenario: Divider on a folded module
- **WHEN** that `cabinet` also has the 26° left inside height fold from 1100 mm and no divider positions
- **THEN** it is accepted, the divider splits the narrowest opening along its span (448 to 782 mm from the module's left face) into two 158 mm bays, its left face is 588 mm from the unbent left side's inner face, the cut list holds `cabinet-divider` 383 × 388 mm, and the confirmat line is 8 + 4 + 4 × 4 + 4 = 32

#### Scenario: Divider cuts into a folded side
- **WHEN** the folded `cabinet` lists `divider_positions_mm` [100] with the divider from shelf 4 to the top
- **THEN** it is refused, naming `modules[0].divider_positions_mm` and the folded side, and no package is created

#### Scenario: Span on a missing shelf
- **WHEN** a module with 2 fixed shelves has `divider_spans` [{`from_board`: 3, `to_board`: "top"}]
- **THEN** it is refused, naming `modules[0].divider_spans`

#### Scenario: Span on an adjustable shelf
- **WHEN** module `cabinet` has 4 adjustable shelves and no fixed shelf, and `divider_spans` [{`from_board`: 4, `to_board`: "top"}]
- **THEN** it is refused, naming `modules[0].divider_spans`, shelf 4, and that only fixed shelves can anchor a divider

#### Scenario: Spans cleared in a revision
- **WHEN** module `cabinet` has the divider from shelf 4 to the top, and the Designer revises it with `divider_spans` []
- **THEN** the proposed version's divider runs from the bottom panel to the top panel, and the change lines name the cleared span

#### Scenario: Divider outside the module
- **WHEN** a module with 964 mm inner width lists a divider at 960 mm
- **THEN** it is refused, naming `modules[0].divider_positions_mm` and the inner width

#### Scenario: Unknown divider field
- **WHEN** a module carries `divider_material`
- **THEN** it is refused, naming `divider_material`, and the refusal becomes a generator-extension request

### Requirement: A module can fold a carcass side at an angle
A module SHALL accept an optional `side_folds` list of at most two entries. Each entry SHALL have:
- `side`: `left` or `right`;
- `from_mm`: a whole millimetre, the kink;
- `along`: `height` or `depth`;
- `angle_deg`: a whole degree from 1 to 89;
- `towards`: `inside` or `outside`.

At most one fold per side. `from_mm` is measured from the module's bottom face when `along` is `height`, and from the module's front face when `along` is `depth`.

The named side SHALL run straight to `from_mm` and then leave its original plane by `angle_deg` from that axis. `inside` moves the side toward the opposite side after the kink; `outside` moves it away. The inset at a run of `h` millimetres past the kink SHALL be `h × tan(angle_deg)`, rounded to the nearest whole millimetre, with halves rounded away from zero.

The module's stated `width`, `height` and `depth` SHALL remain the unbent box (the part before the kink). The build's `overall`, envelope fit, module overlap and room-fit size SHALL use the axis-aligned bounding box of the folded solid, which grows past the stated box when a fold is `outside`.

The folded side SHALL be two rectangular boards joined at the kink, in the carcass material and thickness, at the back-reduced depth. The unfolder side SHALL stay one full-height (or full-depth) rectangle. Each horizontal board (bottom, top, each fixed shelf, each adjustable shelf) SHALL be a rectangle cut to the smallest inner width along that board's thickness, rounded down to a whole millimetre; an adjustable shelf SHALL then be shortened by the adjustable-shelf clearance. The back SHALL be one board whose net outline follows the side profile; its cut-list row SHALL be the grain-aligned bounding rectangle, with notes that name the net shape.

A folded module MAY carry overlay fronts. Each door, flap or drawer front SHALL follow the folded carcass outline in the front plane, with a 3 mm gap (1.5 mm at every edge). Several doors of one entry SHALL split on verticals at equal shares of the unbent width. A front whose outline is a rectangle SHALL stay a rectangular cut-list row, as today. A front whose outline is not a rectangle SHALL be one board whose net follows that outline; its cut-list row SHALL be the grain-aligned bounding rectangle, with notes that name the net shape. A drawer box SHALL stay a rectangle cut to the smallest inner width along that drawer's height, less the runner side clearance.

A folded module MAY carry dividers, full-height or spanning between named boards, as set out in "A module can carry vertical dividers".

A built version SHALL draw those fronts as their own objects in the `fronts` layer, in the front plane, closed; an n-gon front is one mesh named by its cut-list id.

Cut-list row ids:
- with no fold, `{module}-side` quantity 2, as today;
- with a fold, `{module}-side-{left|right}` for an unfolder side, and `{module}-side-{left|right}-lower` plus `{module}-side-{left|right}-upper` (height) or `-front` plus `-back` (depth) for a folded side;
- `{module}-top` and `{module}-bottom` as separate rows when their cut sizes differ, otherwise `{module}-top-bottom` quantity 2 as today;
- without dividers, each fixed or adjustable shelf whose width differs from the others of its kind as its own `{module}-shelf-{n}` or `{module}-adjustable-shelf-{n}` row, lowest first; equal widths keep `{module}-shelf` or `{module}-adjustable-shelf` with quantity, as today; with dividers, shelf rows are grouped by cut width as set out in "A module can carry vertical dividers".

Each joining edge's notes SHALL name the mitre and the angle in degrees. The confirmat count SHALL be 8 per carcass, plus 4 per fold joint, plus 4 per fixed shelf board, plus 4 per divider. The derived assembly SHALL include a step that names the side, the angle and `from_mm`.

A built version SHALL draw the carcass boards as their own objects in the `carcass` and `backs` layers, the upper or back side board rotated by `angle_deg` so it meets the lower or front board at the kink. Dimension lines SHALL follow the folded bounding box.

The document SHALL be refused, naming the field and the problem, when:
- two entries name the same side;
- `along` is `height` and `from_mm` is not strictly between the carcass thickness and height minus that thickness;
- `along` is `depth` and `from_mm` is not strictly between 1 mm and the back-reduced depth;
- the inset at the far end rounds to 0 mm;
- the inner opening at any point along the fold is less than 1 mm;
- a front's remaining width at any height along that front is below the minimum front size;
- the folded bounding box lies outside the envelope, or overlaps another module's folded bounding box.

`revise_package` SHALL be able to set `side_folds` to a new list. `[]` SHALL clear every fold. A module with no `side_folds` SHALL derive and be drawn exactly as before.

#### Scenario: Left side 26 degrees from 1100 mm
- **WHEN** module `cabinet` is 800 × 2000 × 400 mm with 18 mm carcass, 12 mm back, no shelves, and one fold `{side: left, from_mm: 1100, along: height, angle_deg: 26, towards: inside}`
- **THEN** it is accepted, the left-side inset at the top is 439 mm, the cut list holds `cabinet-side-left-lower` 1100 × 388 mm, `cabinet-side-left-upper` 1001 × 388 mm with notes naming a 26° mitre, `cabinet-side-right` 2000 × 388 mm, separate top and bottom rows, and the confirmat line is 12

#### Scenario: Outside fold grows overall
- **WHEN** the same module's fold is `towards: outside` and the document has no envelope
- **THEN** `overall` width is 800 + 439 = 1239 mm

#### Scenario: Fold pinches the opening
- **WHEN** a 400 mm wide module with 18 mm carcass has a left inside height fold from 100 mm at 45°
- **THEN** it is refused, naming `modules[0].side_folds` and the remaining inner width, and no package is created

#### Scenario: Two doors follow a left height fold
- **WHEN** the 800 × 2000 × 400 mm cabinet has the 26° left inside height fold from 1100 mm and two hinged doors
- **THEN** it is accepted, the right door is a rectangle, the left door's net follows the left profile with a 3 mm gap, its cut-list row is the bounding rectangle with notes naming the net, and a built version draws both in the `fronts` layer

#### Scenario: Adjustable shelf on a fold uses the pinched width
- **WHEN** that cabinet has one adjustable shelf whose board sits above 1100 mm
- **THEN** the adjustable-shelf row is cut to the smallest inner width along that board, less the adjustable-shelf clearance

#### Scenario: Front too narrow at the top is refused
- **WHEN** a folded module has a door whose remaining width at some height along that door is below the minimum front size
- **THEN** it is refused, naming `modules[0].fronts`, and no package is created

#### Scenario: Dividers accepted on a folded module
- **WHEN** a module with a side fold also lists `dividers` 1 and the divider fits inside the folded opening along its whole span
- **THEN** it is accepted, and the cut list holds a divider row

#### Scenario: Two folds on the same side
- **WHEN** `side_folds` lists two entries with `side: left`
- **THEN** it is refused, naming `modules[0].side_folds`

#### Scenario: Fold drawn in the model
- **WHEN** a version with the 26° left height fold is built headless
- **THEN** the model holds the lower and upper left-side objects meeting at 1100 mm, the upper board at 26° to vertical, and the back's net outline follows the left profile

#### Scenario: Folds cleared in a revision
- **WHEN** module `cabinet` has a left fold and the Designer revises it with `side_folds` []
- **THEN** the proposed version has no folds, the change lines name the cleared fold, and the sides go back to one `{id}-side` row of quantity 2

#### Scenario: Old document unchanged
- **WHEN** a document with no `side_folds` is derived and built
- **THEN** its cut list, hardware, assembly, `overall` and model equal those of the same document before this change

## ADDED Requirements

### Requirement: A module can state each shelf's kind
A module SHALL accept an optional `shelf_kinds`: one entry per shelf, lowest first, each `"fixed"` or `"adjustable"`. The number of entries SHALL equal `shelves` plus `adjustable_shelves`, and the number of each kind SHALL equal its count. Without `shelf_kinds`, the fixed shelves SHALL take the lowest heights and the adjustable shelves the rest, as before. Shelf heights (even spacing, `shelf_spacing_mm` or `shelf_positions_mm`) SHALL NOT depend on the kinds.

Each shelf SHALL be derived and drawn by its own kind: a fixed shelf as a fixed-shelf board with 4 confirmat screws, an adjustable shelf as an adjustable-shelf board less the clearance, with its pins. `revise_package` SHALL be able to set `shelf_kinds`; `[]` SHALL clear it back to fixed shelves lowest. The document SHALL be refused, naming `shelf_kinds`, when its length or its kind counts disagree with `shelves` and `adjustable_shelves`. A module without `shelf_kinds` SHALL derive and be drawn exactly as before.

#### Scenario: Top shelf fixed, the rest adjustable
- **WHEN** module `cabinet` had 4 adjustable shelves and is revised to `shelves` 1, `adjustable_shelves` 3 and `shelf_kinds` ["adjustable", "adjustable", "adjustable", "fixed"]
- **THEN** the cut list holds one fixed-shelf board and three adjustable-shelf boards at the same heights as before, the confirmat line rises by 4, the shelf-pin line counts 3 shelves instead of 4, and the top board in the model is the fixed one

#### Scenario: Kinds disagree with the counts
- **WHEN** a module with `shelves` 1 and `adjustable_shelves` 3 lists `shelf_kinds` ["fixed", "fixed", "adjustable", "adjustable"]
- **THEN** it is refused, naming `modules[0].shelf_kinds`

#### Scenario: No kinds, unchanged
- **WHEN** a document has no `shelf_kinds`
- **THEN** its cut list, hardware and model equal those of the same document before this change

### Requirement: A revision preview lists hardware and cut-list changes
The confirmation `revise_package` shows SHALL list, after the change lines, every hardware line whose quantity changes (item, old quantity → new quantity, or added / removed) and every cut-list row that is added, removed or changes quantity or size, derived from the latest version and the revised document. A revision that changes no hardware or cut-list row SHALL show no such lines.

#### Scenario: Fixing a shelf in the preview
- **WHEN** the owner agrees to fix the top of four adjustable shelves and the Designer proposes the revision
- **THEN** the preview lists the confirmat line rising by 4, the shelf-pin line falling by one shelf's pins, a fixed-shelf row added and the adjustable-shelf quantity falling from 4 to 3

#### Scenario: Divider in the preview
- **WHEN** the Designer proposes the divider from shelf 4 to the top on `cabinet`
- **THEN** the preview lists `cabinet-divider` 383 × 388 mm added and the confirmat line 24 → 28
