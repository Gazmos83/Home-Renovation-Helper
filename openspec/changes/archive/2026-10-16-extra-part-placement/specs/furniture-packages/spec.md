## ADDED Requirements

### Requirement: An extra part can state where each of its pieces sits
A custom-build extra part SHALL accept optional `placements`: a list with exactly one entry per piece, so its length equals the part's `qty`. A piece is described in its own terms: its length, its width, and its thickness from the part's material slot. Its reference corner is the corner at the start of its length, on the edge and face it is measured from. Each entry SHALL give:
- `x`, `y`, `z`: where the reference corner sits, in mm in the build's frame, as for modules and wall shelves (x to the right, y towards the back, z up);
- `length_along` and `width_along`: the axis (`x`, `y` or `z`) the piece's length and width run along before any turn, never the same; the thickness runs along the remaining axis;
- optionally `roll_deg` (−89 to 89, not 0): the piece turns about its own length line through the reference corner, a positive angle turning its width towards its thickness side;
- optionally `tilt`: `towards` (an axis other than `length_along`) and `angle_deg` (−89 to 89, not 0). After any roll, the piece's length turns about the reference corner towards that axis by that angle, a positive angle towards the axis's positive direction. "Length along x, tilt 35° towards z" is a brace rising to the right.

A document whose placements disagree with `qty`, whose `length_along` equals `width_along`, or whose `tilt.towards` equals `length_along`, SHALL be refused naming the field. When the document has an envelope, a placed piece SHALL be refused, naming the part, unless every corner of the piece after its turns lies inside the envelope. When it has no envelope, the overall size SHALL include every corner of every placed piece after its turns. Unplaced pieces SHALL NOT count.

A build SHALL draw each placed piece at its stated position, orientation and turns, as exact geometry. Each piece is one object named by its cut-list id, as for every other part, under the extras empty and in the `extras` layer. An extra part without `placements` SHALL still be laid flat beside the build. Placements SHALL NOT change any cut-list row's quantity, length, width, thickness or material, nor the hardware, the drilling list or the pricing.

A part override that changes an extra part's quantity SHALL keep the existing rule: the drawing follows the overridden count, extra copies are added beside the last piece and surplus pieces are dropped.

#### Scenario: Placed frame drawn assembled
- **WHEN** a document has extra part `top-frame` (qty 1, 1200 × 60 mm, 18 mm slot) placed at x 0, y 0, z 900, length along x, width along y
- **THEN** `model.blend`, `model.glb` and `screenshot.png` show `top-frame` as a 1200 × 60 × 18 mm board with its corner at (0, 0, 900) in the build's frame, and not beside the build

#### Scenario: Upright piece
- **WHEN** extra part `post` (qty 1, 900 × 45 mm) is placed with length along z and width along y
- **THEN** the board stands 900 mm tall, 45 mm deep and as thick as its slot in x

#### Scenario: Diagonal brace
- **WHEN** extra part `brace` (qty 1, 1000 × 60 mm, 18 mm slot) is placed at x 100, y 0, z 0, length along x, width along y, with tilt 30° towards z
- **THEN** the drawn brace's far end is 866 mm right of and 500 mm above its reference corner, its width still runs along y, and the overall height without an envelope includes it

#### Scenario: Rolled trim strip
- **WHEN** extra part `cove` (qty 1, 1200 × 40 mm) is placed with length along x and width along y, and `roll_deg` 45
- **THEN** the strip's width rises from its reference edge at 45° between y and z, and its length still runs along x

#### Scenario: Turned piece leaves the envelope
- **WHEN** the envelope is 1000 mm high and a placed piece 1200 mm long, length along x, with tilt 60° towards z, starts at z 0
- **THEN** the document is refused naming the part and saying it lies outside the envelope

#### Scenario: Tilt towards its own length axis
- **WHEN** a placement has length along x and tilt towards x
- **THEN** the document is refused naming `tilt.towards`

#### Scenario: Unplaced part unchanged
- **WHEN** a document has extra part `spare-trim` without `placements`
- **THEN** it is laid flat beside the build as before, and the build's overall size ignores it

#### Scenario: Placement count disagrees with quantity
- **WHEN** extra part `slat` has qty 4 and 3 placements
- **THEN** the document is refused naming `extra_parts[n].placements` and saying 4 are needed, and Blender is not started

#### Scenario: Placed piece outside the envelope
- **WHEN** the envelope is 1200 mm wide and a placed piece runs from x 300 for 1000 mm along x
- **THEN** the document is refused naming the part and saying it lies outside the envelope

#### Scenario: Cut list unchanged by placement
- **WHEN** the same document is derived with and without `placements` on its extra parts
- **THEN** both give the same cut-list rows, hardware lines and drilling list

### Requirement: An extra part can state angled end cuts
An extra part SHALL accept optional `end_cuts`, the same for every piece of the part:
- `across`: `width` or `thickness`, the side the ends are cut across;
- `start_deg` and `end_deg`, each −89 to 89, where 0 is a square end.

A positive angle shortens the edge opposite the reference edge by `size × tan(angle)`, where `size` is the width or thickness the cut runs across. A negative angle shortens the reference edge by the same amount. The stated `length` is always the longest edge, so the cut-list length is unchanged. Two cuts that shorten the same edge to zero or less SHALL be refused, naming the part. The same applies to one cut that shortens an edge to zero or less.

A build SHALL draw each piece of the part with its ends cut as stated, both when placed and when laid beside the build. The part's cut-list row SHALL carry the end cuts in its notes, for example "ends cut 35° / −35° across width". Its quantity, length, width, thickness and material SHALL stay unchanged.

#### Scenario: Brace cut to sit flush between posts
- **WHEN** extra part `brace` (1000 × 60 mm) has `end_cuts` across width with start 30° and end −30°, and is placed with length along x, width along z and tilt 30° towards z between two upright posts
- **THEN** the drawn brace is a parallelogram in its face whose ends stand plumb against the posts, and its cut-list row says "ends cut 30° / −30° across width" with length 1000

#### Scenario: Brace cut to sit flush on rails
- **WHEN** the same brace instead has start 60° and end −60° (90° less the tilt)
- **THEN** its ends lie level, flush with horizontal rails above and below

#### Scenario: Mitred frame member
- **WHEN** extra part `stile` (600 × 50 mm) has `end_cuts` across width with start 45° and end 45°
- **THEN** each piece is drawn as a trapezoid whose reference edge is 600 mm and whose opposite edge is 500 mm

#### Scenario: Cuts that consume the piece
- **WHEN** extra part `stub` (80 × 60 mm) has `end_cuts` across width with start 45° and end 45°
- **THEN** the document is refused naming `stub` and saying the end cuts leave no length

### Requirement: A protruding-shelf fit moves placed extra parts with the build
When a revision is fitted to a board that reaches in front of the build's front plane, every placed extra-part piece's `y` SHALL rise by the same amount as the modules and wall shelves, so the pieces stay where they sit on the build. The revision confirmation SHALL carry one fit line per moved part. Unplaced extra parts SHALL NOT change.

#### Scenario: Placed frame moves back with the cabinet
- **WHEN** module `cabinet` gets a shelf that protrudes 162 mm and extra part `top-frame` is placed at y 0
- **THEN** `cabinet`'s `y` and `top-frame`'s placement `y` both become 162, and the confirmation says `top-frame`'s pieces move back 162 mm
