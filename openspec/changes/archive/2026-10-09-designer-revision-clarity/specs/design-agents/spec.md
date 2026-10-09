## MODIFIED Requirements

### Requirement: The Designer revises a piece from stated changes
`revise_package` SHALL take the piece's package id and a bounded set of changes — the name, the envelope, a material slot, per module (by its id) any field, modules to add or remove, extra parts, part overrides — apply them to a copy of the latest version's document, refuse naming an unknown module or part id, validate the result, preview the change lines and pause for `yes`. On `yes` the next version is recorded as revised from the latest and built; the earlier version's folder and record are untouched. Only the round's first revision call is offered; a second in the same round is answered as not created.

A requested field whose value equals the latest version's value SHALL be dropped and SHALL give no change line. When every requested change is dropped this way, the revision SHALL be refused with a message saying nothing would change. No confirmation is raised and no version is created.

A change line for a module's `fronts` or `hardware` SHALL describe the list before and after the change, not only its length. A front is named by its type, count, opening or hinged side, height when set, and hinge item when it is not the default. A hardware line is named by its id, item and quantity.

#### Scenario: Shelves changed
- **WHEN** the owner says "three shelves in the cabinet" and confirms
- **THEN** version 2 exists with "cabinet: shelves 2 → 3" and version 1 is unchanged

#### Scenario: Unknown module
- **WHEN** the change names module `drawers` which the piece does not have
- **THEN** it is refused naming `drawers` and listing the piece's modules, and no confirmation is raised

#### Scenario: Fronts change shown in full
- **WHEN** module `cabinet` has two hinged doors and the change replaces them with one hinged door and one 200 mm drawer
- **THEN** the confirmation lists "cabinet: fronts" with "2 doors (hinge)" before and "1 door (hinge), 1 drawer 200 mm" after, and no line reads "entries"

#### Scenario: Hardware change shown in full
- **WHEN** a module's hardware line `handle` changes quantity from 2 to 4
- **THEN** the change line names `handle`, its item, "×2" before and "×4" after

#### Scenario: No-op field dropped
- **WHEN** the change sets `cabinet` height to its current 2238 and shelves from 6 to 3
- **THEN** the confirmation lists only "cabinet: shelves 6 → 3"

#### Scenario: Revision that changes nothing
- **WHEN** every requested field equals the latest version's value
- **THEN** the tool refuses saying nothing would change, no confirmation is raised, and no version is created

## ADDED Requirements

### Requirement: The Designer confirms the change list before revising
Before calling `revise_package`, the Designer SHALL restate the changes it understood as a list and ask the owner whether anything else should change. It SHALL call `revise_package` only after the owner says the list is complete. That one call SHALL carry every change asked for since the last created revision. When the owner answers with a further change, the Designer SHALL add it to the list and ask again. When the owner declines a revision with a reason, the Designer SHALL treat the reason as one more change, restate the whole list and ask again, and SHALL NOT call `revise_package` again in that reply.

#### Scenario: Change restated first
- **WHEN** the owner asks "make the cabinet 600 wide"
- **THEN** the Designer's reply restates "cabinet: width → 600 mm", asks whether anything else should change, and no confirmation is raised

#### Scenario: Changes gathered into one call
- **WHEN** the owner then adds "and three shelves", and then says that is all
- **THEN** one `revise_package` call carries both the width and the shelves, and one confirmation lists both

#### Scenario: Decline reason becomes a change
- **WHEN** the owner answers the confirmation with no and the reason "keep two shelves"
- **THEN** no version is created, and the Designer's reply restates the list with the shelves change corrected and asks again without raising a new confirmation in that reply

### Requirement: The Designer sees the active build's latest version
Each Designer turn SHALL carry a summary of the active build's latest version, built by the application from that version's stored document. The summary SHALL give:
- per module: its id, name, size, position, carcass slot, fixed and adjustable shelves, each front (type, count, opening or hinged side, height when set, hinge item), and its hardware lines (id, item, quantity);
- each wall shelf (id, length, depth, material slot, bracket item, and owner bracket positions when set);
- each extra part by id;
- each material slot with its material and thickness;
- each part override by id.

Only the active build SHALL be summarised; other builds stay one line each. Owner-authored text in the summary SHALL be neutralised. The summary SHALL be labelled as application data, never as an instruction. When the conversation has no active build, or its latest version has no readable document, no summary SHALL be given and the Designer's context SHALL say so.

#### Scenario: Module and fronts visible
- **WHEN** the active build `listening-wall` v7 has module `cabinet` 600×2238×400 mm with 3 shelves and one hinged door
- **THEN** the Designer's context names `cabinet`, its size, "3 shelves" and "1 door (hinge)" for v7

#### Scenario: Only the active build summarised
- **WHEN** the conversation's builds are `hall-bench` (active) and `shoe-rack`
- **THEN** the Designer's context summarises `hall-bench`'s modules, and `shoe-rack` appears only as its one line

#### Scenario: Delimiter in a module name
- **WHEN** a module's name contains the untrusted-content delimiter
- **THEN** the summary shows it neutralised

#### Scenario: No readable document
- **WHEN** the active build's latest version has no readable document
- **THEN** the Designer's context says the piece's contents could not be read, and no module is listed
