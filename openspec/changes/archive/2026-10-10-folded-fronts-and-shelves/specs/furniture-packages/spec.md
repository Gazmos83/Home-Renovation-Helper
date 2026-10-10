## MODIFIED Requirements

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

A built version SHALL draw those fronts as their own objects in the `fronts` layer, in the front plane, closed; an n-gon front is one mesh named by its cut-list id.

Cut-list row ids:
- with no fold, `{module}-side` quantity 2, as today;
- with a fold, `{module}-side-{left|right}` for an unfolder side, and `{module}-side-{left|right}-lower` plus `{module}-side-{left|right}-upper` (height) or `-front` plus `-back` (depth) for a folded side;
- `{module}-top` and `{module}-bottom` as separate rows when their cut sizes differ, otherwise `{module}-top-bottom` quantity 2 as today;
- each fixed or adjustable shelf whose width differs from the others of its kind as its own `{module}-shelf-{n}` or `{module}-adjustable-shelf-{n}` row, lowest first; equal widths keep `{module}-shelf` or `{module}-adjustable-shelf` with quantity, as today.

Each joining edge's notes SHALL name the mitre and the angle in degrees. The confirmat count SHALL be 8 per carcass, plus 4 per fold joint, plus 4 per fixed shelf board. The derived assembly SHALL include a step that names the side, the angle and `from_mm`.

A built version SHALL draw the carcass boards as their own objects in the `carcass` and `backs` layers, the upper or back side board rotated by `angle_deg` so it meets the lower or front board at the kink. Dimension lines SHALL follow the folded bounding box.

The document SHALL be refused, naming the field and the problem, when:
- two entries name the same side;
- `along` is `height` and `from_mm` is not strictly between the carcass thickness and height minus that thickness;
- `along` is `depth` and `from_mm` is not strictly between 1 mm and the back-reduced depth;
- the inset at the far end rounds to 0 mm;
- the inner opening at any point along the fold is less than 1 mm;
- the module has dividers;
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

#### Scenario: Dividers refused on a folded module
- **WHEN** a module with a side fold also lists `dividers` 1
- **THEN** it is refused, naming `modules[0].dividers`, and no package is created

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
