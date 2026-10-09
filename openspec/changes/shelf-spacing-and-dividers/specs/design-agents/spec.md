## ADDED Requirements

### Requirement: Requested shelf and divider measurements are checked
The requested-measurement check SHALL accept as a field of a module:
- `shelf_spacing_mm`;
- `shelf_positions_mm`;
- `divider_positions_mm`.

These fields have the following rules:
- **A field the module has not set yet.** An absolute length SHALL be accepted, and the revised document SHALL hold that value. A relative length ("5 cm more") SHALL be refused, naming the field as not set in the latest version.
- **A positions list.** The entry SHALL give one requested position. The check SHALL pass when the revised list holds that value. An owner's message with several positions SHALL be covered by one entry per position.

Every other rule of "A revision carries the owner's measurements and code checks them" SHALL apply unchanged.

#### Scenario: Spacing on a module that had none
- **WHEN** module `cabinet` has 4 shelves and no spacing, the owner wrote "4 shelves 355 mm apart", and the entry quotes it with `cabinet`, `shelf_spacing_mm`, 355, and the changes set `shelf_spacing_mm` 355
- **THEN** the check passes and the confirmation is raised with "cabinet: shelf_spacing_mm not set → 355"

#### Scenario: Invented spacing refused
- **WHEN** the owner wrote "355 mm apart" and the changes set `shelf_spacing_mm` 373
- **THEN** the call is refused naming "355 mm apart", 355 expected and 373 set

#### Scenario: Divider position covered
- **WHEN** the owner wrote "a divider 400 mm from the left", and the entry quotes it with `cabinet`, `divider_positions_mm`, 400, and the changes set `divider_positions_mm` [400]
- **THEN** the check passes

## MODIFIED Requirements

### Requirement: The Designer sees the active build's latest version
Each Designer turn SHALL carry a summary of the active build's latest version, built by the application from that version's stored document. The summary SHALL give:
- the envelope: its width, height and depth in millimetres;
- per module: its id, name, size, position, carcass slot, fixed and adjustable shelves, its shelf spacing or shelf positions when set, its dividers with their positions when set, each front (type, count, opening or hinged side, height when set, hinge item), and its hardware lines (id, item, quantity);
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
