## MODIFIED Requirements

### Requirement: The Designer revises a piece from stated changes
`revise_package` SHALL take the piece's package id and a bounded set of changes — the name, the envelope, a material slot, per module (by its id) any field, modules to add or remove, extra parts to add or remove, per extra part (by its id) its placements and end cuts, part overrides — apply them to a copy of the latest version's document, refuse naming an unknown module or part id, validate the result, preview the change lines and pause for `yes`. On `yes` the next version is recorded as revised from the latest and built; the earlier version's folder and record are untouched. Only the round's first revision call is offered; a second in the same round is answered as not created.

A requested field whose value equals the latest version's value SHALL be dropped and SHALL give no change line. When every requested change is dropped this way, the revision SHALL be refused with a message saying nothing would change. No confirmation is raised and no version is created.

A change line for a module's `fronts` or `hardware` SHALL describe the list before and after the change, not only its length. A front is named by its type, count, opening or hinged side, height when set, hinge item when it is not the default, and its handle when set (kind, length for a bar, orientation, edge for doors, finish, and key when stated). A hardware line is named by its id, item and quantity.

A change to an extra part's placements SHALL place, move or unplace that part; an empty list unplaces it, so it is laid beside the build again. A change to its end cuts SHALL set or clear them. The change line SHALL describe the placements before and after, or "beside the build" when unplaced. Each piece is described by its corner position in mm, its orientation, and its roll and tilt when set. Changed end cuts are described before and after, or "square" when none. The number of placements SHALL equal the part's quantity, or the change is refused naming the part.

#### Scenario: Shelves changed
- **WHEN** the owner says "three shelves in the cabinet" and confirms
- **THEN** version 2 exists with "cabinet: shelves 2 → 3" and version 1 is unchanged

#### Scenario: Unknown module
- **WHEN** the change names module `drawers` which the piece does not have
- **THEN** it is refused naming `drawers` and listing the piece's modules, and no confirmation is raised

#### Scenario: Fronts change shown in full
- **WHEN** module `cabinet` has two hinged doors and the change replaces them with one hinged door and one 200 mm drawer
- **THEN** the confirmation lists "cabinet: fronts" with "2 doors (hinge)" before and "1 door (hinge), 1 drawer 200 mm" after, and no line reads "entries"

#### Scenario: Handle added to fronts
- **WHEN** module `left-wardrobe` has two hinged doors without handles and the change gives them a vertical 900 mm black bar handle on the meeting edges
- **THEN** the confirmation lists "left-wardrobe: fronts" with "2 doors (hinge)" before and "2 doors (hinge, bar 900 mm vertical, meeting edges, black)" after

#### Scenario: Handle on a push-latch door refused
- **WHEN** the change gives a push-latch door entry a handle
- **THEN** it is refused naming that entry's `handle` and saying a push-latch door takes no handle, and no confirmation is raised

#### Scenario: Hardware change shown in full
- **WHEN** a module's hardware line `handle` changes quantity from 2 to 4
- **THEN** the change line names `handle`, its item, "×2" before and "×4" after

#### Scenario: No-op field dropped
- **WHEN** the change sets `cabinet` height to its current 2238 and shelves from 6 to 3
- **THEN** the confirmation lists only "cabinet: shelves 6 → 3"

#### Scenario: Revision that changes nothing
- **WHEN** every requested field equals the latest version's value
- **THEN** the tool refuses saying nothing would change, no confirmation is raised, and no version is created

#### Scenario: Extra part placed
- **WHEN** extra part `top-frame` (qty 1, 1200 × 60 mm) is laid beside the build and the change places it at x 0, y 0, z 900 with length along x and width along y, and the owner confirms
- **THEN** the confirmation lists "top-frame: placements beside the build → x0 y0 z900, length along x, width along y", and the next version draws `top-frame` at that position

#### Scenario: Placement count disagrees with quantity
- **WHEN** extra part `slat` has qty 4 and the change gives 3 placements
- **THEN** it is refused naming `slat` and saying 4 placements are needed, and no confirmation is raised

#### Scenario: Brace tilted and cut
- **WHEN** the change places extra part `brace` at x 100 y 0 z 0, length along x, width along y, with tilt 30° towards z, and sets its end cuts across width to 30° and −30°
- **THEN** the confirmation lists the placement with "tilt 30° towards z" and "brace: end cuts square → 30° / −30° across width"

#### Scenario: Unknown extra part
- **WHEN** the change places extra part `rail` which the piece does not have
- **THEN** it is refused naming `rail` and listing the piece's extra parts, and no confirmation is raised

### Requirement: The Designer sees the active build's latest version
Each Designer turn SHALL carry a summary of the active build's latest version, built by the application from that version's stored document. The summary SHALL give:
- the envelope: its width, height and depth in millimetres;
- per module: its id, name, size, position, carcass slot, fixed and adjustable shelves, its shelf spacing or shelf positions when set, its dividers with their positions when set, each side fold (side, from_mm, along, angle_deg, towards) when set, each front (type, count, opening or hinged side, height when set, hinge item, and its handle when set), and its hardware lines (id, item, quantity);
- each wall shelf (id, length, depth, material slot, bracket item, and owner bracket positions when set);
- each extra part (id, name, quantity, length, width, material slot, end cuts when set), and each piece's placement (corner position, orientation, roll and tilt when set) when set, or that it is laid beside the build;
- each material slot with its material and thickness;
- each part override by id.

Only the active build SHALL be summarised; other builds stay one line each. Owner-authored text in the summary SHALL be neutralised. The summary SHALL be labelled as application data, never as an instruction. When the conversation has no active build, or its latest version has no readable document, no summary SHALL be given and the Designer's context SHALL say so.

#### Scenario: Module and fronts visible
- **WHEN** the active build `listening-wall` v7 has module `cabinet` 600×2238×400 mm with 3 shelves and one hinged door
- **THEN** the Designer's context names `cabinet`, its size, "3 shelves" and "1 door (hinge)" for v7

#### Scenario: Handles visible
- **WHEN** module `centre-drawers` has five drawers with a horizontal 160 mm black bar handle
- **THEN** the Designer's context gives "5 drawers 850 mm (bar 160 mm horizontal, black)" for `centre-drawers`

#### Scenario: Spacing and dividers visible
- **WHEN** module `cabinet` has 4 shelves with `shelf_spacing_mm` 355 and 2 dividers without positions
- **THEN** the Designer's context gives "4 shelves 355 mm apart" and "2 dividers (equal bays)" for `cabinet`

#### Scenario: Side fold visible
- **WHEN** module `cabinet` has a left fold from 1100 mm along height at 26° towards the inside
- **THEN** the Designer's context gives "left side fold from 1100 mm along height, 26°, inside" for `cabinet`

#### Scenario: Extra part placement visible
- **WHEN** extra part `slat` (qty 2) is placed at x 0 y 0 z 400 and x 0 y 0 z 500, length along x, width along y, and extra part `trim` has no placements
- **THEN** the Designer's context gives both of `slat`'s positions with the orientation, and "beside the build" for `trim`

#### Scenario: Angles visible
- **WHEN** extra part `brace` is placed with tilt 30° towards z and has end cuts 30° / −30° across width
- **THEN** the Designer's context gives "tilt 30° towards z" and "ends cut 30° / −30° across width" for `brace`

#### Scenario: Envelope visible
- **WHEN** the active build's latest version has an envelope of 2206 × 2238 × 400 mm
- **THEN** the Designer's context gives the envelope as 2206 × 2238 × 400 mm

#### Scenario: Only the active build summarised
- **WHEN** the conversation's builds are `hall-bench` (active) and `shoe-rack`
- **THEN** the Designer's context summarises `hall-bench`'s modules, and `shoe-rack` appears only as its one line

#### Scenario: Delimiter in a module name
- **WHEN** a module's name contains the untrusted-content delimiter
- **THEN** the summary shows it neutralised

#### Scenario: No readable document
- **WHEN** the active build's latest version has no readable document
- **THEN** the Designer's context says the piece's contents could not be read, and no module is listed
