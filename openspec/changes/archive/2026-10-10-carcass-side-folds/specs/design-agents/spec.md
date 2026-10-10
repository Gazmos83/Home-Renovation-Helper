## ADDED Requirements

### Requirement: Requested side-fold measurements are checked
The requested-measurement check SHALL accept `side_folds` as a field of a module. The entry SHALL give one requested `from_mm`. The check SHALL pass when the revised list holds a fold with that `from_mm`. An owner's message with several such lengths SHALL be covered by one entry per length.

A module that has no folds yet SHALL accept an absolute length, and the revised document SHALL hold that value. A relative length ("5 cm more") SHALL be refused, naming the field as not set in the latest version.

An angle in degrees SHALL NOT be treated as a length. Every other rule of "A revision carries the owner's measurements and code checks them" SHALL apply unchanged.

#### Scenario: Bend datum on a module that had no fold
- **WHEN** module `cabinet` has no folds, the owner wrote "The left side of the carcass should have a 26 degree bend from 1100 mm", the entry quotes "1100 mm" with `cabinet`, `side_folds`, 1100, and the changes set a left fold with `from_mm` 1100
- **THEN** the check passes and the confirmation is raised

#### Scenario: Invented datum refused
- **WHEN** the owner wrote "from 1100 mm" and the changes set `from_mm` 1000
- **THEN** the call is refused naming "1100 mm", 1100 expected and 1000 set

#### Scenario: Relative fold datum refused when unset
- **WHEN** module `cabinet` has no folds, the owner wrote "5 cm higher", and the entry uses `side_folds` as a relative change
- **THEN** the call is refused naming `side_folds` as not set in the latest version

## MODIFIED Requirements

### Requirement: The Designer sees the active build's latest version
Each Designer turn SHALL carry a summary of the active build's latest version, built by the application from that version's stored document. The summary SHALL give:
- the envelope: its width, height and depth in millimetres;
- per module: its id, name, size, position, carcass slot, fixed and adjustable shelves, its shelf spacing or shelf positions when set, its dividers with their positions when set, each side fold (side, from_mm, along, angle_deg, towards) when set, each front (type, count, opening or hinged side, height when set, hinge item), and its hardware lines (id, item, quantity);
- each wall shelf (id, length, depth, material slot, bracket item, and owner bracket positions when set);
- each extra part by id;
- each material slot with its material and thickness;
- each part override by id.

Only the active build SHALL be summarised; other builds stay one line each. Owner-authored text in the summary SHALL be neutralised. The summary SHALL be labelled as application data, never as an instruction. When the conversation has no active build, or its latest version has no readable document, no summary SHALL be given and the Designer's context SHALL say so.

#### Scenario: Module and fronts visible
- **WHEN** the active build `listening-wall` v7 has module `cabinet` 600×2238×400 mm with 3 shelves and one hinged door
- **THEN** the Designer's context names `cabinet`, its size, "3 shelves" and "1 door (hinge)" for v7

#### Scenario: Spacing and dividers visible
- **WHEN** module `cabinet` has 4 shelves with `shelf_spacing_mm` 355 and 2 dividers without positions
- **THEN** the Designer's context gives "4 shelves 355 mm apart" and "2 dividers (equal bays)" for `cabinet`

#### Scenario: Side fold visible
- **WHEN** module `cabinet` has a left fold from 1100 mm along height at 26° towards the inside
- **THEN** the Designer's context gives "left side fold from 1100 mm along height, 26°, inside" for `cabinet`

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
