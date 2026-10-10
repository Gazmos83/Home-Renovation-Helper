# cut-list-pricing Specification

## Purpose
Defines how a package version's cut list and hardware are priced: packing parts onto sheets and remnants, classifying cuts against the home store, the cut-charge choice, edge banding, hardware and delivery, completeness, and the immutable pricing record.

## Requirements

### Requirement: A version's cut list is priced against the price list
Pricing a package version SHALL read its derived cut-list and hardware rows, map each part's material to a price-list key, pack the parts of each sheet material onto that material's sheets with saw kerf, grain-locked parts keeping their direction, remnants of the same material used before new sheets, and SHALL return per material the sheets bought, utilisation and cost, plus hardware, edge banding (rounded up to whole bundles), cut-service and delivery lines, and the total in cents. Starting no Blender process.

#### Scenario: Desk priced
- **WHEN** the fold-down desk version 1 is priced with every material and hardware entry present
- **THEN** the pricing is complete, lists the birch sheets bought with utilisation, the hardware lines, and a total in cents

#### Scenario: Remnant used first
- **WHEN** a matching remnant on the rack holds a part
- **THEN** that part is placed on the remnant and fewer new sheets are bought; the rack's quantity is not changed by pricing

### Requirement: Missing prices make a pricing incomplete, never guessed
A part, hardware line or band whose material has no price-list entry, a hardware line with no quantity, a part too large for any sheet, a cut whose service cannot be determined, or, in `per_cut` mode, hinge cup borings with no captured hinge-boring price SHALL be listed by name, counted, and SHALL mark the pricing incomplete; no price SHALL be invented for it.

#### Scenario: Unknown hardware
- **WHEN** a hardware line has no entry
- **THEN** the pricing is incomplete and lists that line as unpriced by its id

#### Scenario: Hardware line without a quantity
- **WHEN** a shelf-pin line has no quantity because its data sheet lacks the pins per shelf
- **THEN** the pricing is incomplete and lists that line as unpriced, saying its quantity could not be resolved

#### Scenario: No hinge-boring price
- **WHEN** a version with hinges is priced in `per_cut` mode and the home store has no captured hinge-boring price
- **THEN** the pricing is incomplete and lists the hinge borings as unpriced

### Requirement: Cuts are classified against the home store
Each cut SHALL be classified as `covered`, `custom` or `undetermined` against the configured home toom store's captured cut services and the owner's restrictions for that store, the owner's restriction outranking the captured service; a part whose notes name machining (holes, cut-outs, mitres, grommets) SHALL be marked for review. The cut charge SHALL follow the chosen mode: `shared` (no per-cut fee) or `per_cut` (the straight-cut price times the cut count); with no mode chosen the pricing SHALL say the choice is open.

#### Scenario: Restriction outranks the service
- **WHEN** the store's captured services include straight cuts but the owner records that this store does not cut panels thicker than 25 mm
- **THEN** a 27 mm worktop cut is `custom`

#### Scenario: Derived mitre notes marked for review
- **WHEN** a version whose cut list includes a side-upper row with notes naming a 26° mitre is priced
- **THEN** that row is marked for review

### Requirement: A pricing is an immutable record
Each pricing SHALL be stored as a new record for its package version with the time, the home store, the cut-charge mode, every entry it used (at the price used) and its totals, and SHALL never change afterwards; repricing makes a new record.

#### Scenario: Reprice after an override
- **WHEN** an override changes and the version is priced again
- **THEN** a second record exists with the new total and the first is unchanged

### Requirement: The remnant rack is changed only on confirmation
The owner's remnant rack SHALL hold offcuts by material key, length, width, grain axis and quantity. The Researcher's `manage_remnants` SHALL list freely and SHALL pause for the owner's `yes` before adding or removing a remnant; the owner MAY also add and remove remnants directly.

#### Scenario: Add via chat
- **WHEN** the Researcher proposes adding a 600 × 400 mm birch offcut
- **THEN** the turn pauses and the rack is unchanged until the owner answers `yes`

### Requirement: Hinge cup borings are charged with the cut service
Pricing a version SHALL read its hinge cup boring count from the version's drilling list. In `per_cut` mode, it SHALL add one cut-service line: the count times the home store's captured hinge-boring (`topfband_bohrung`) price. In `shared` mode, the line SHALL show the count with no fee. Shelf-pin holes SHALL be listed with their count and no fee, since toom offers no service for them; when the hole heights are a rule in words, they SHALL be listed with no count, and this SHALL NOT mark the pricing incomplete. A version with no hinges SHALL have no hinge-boring line.

#### Scenario: Borings charged per cut
- **WHEN** a version with 8 hinges is priced in `per_cut` mode and the home store's hinge-boring service has a captured price
- **THEN** the pricing holds a hinge-boring line of 8 times that price, and the total includes it

#### Scenario: Borings in shared mode
- **WHEN** the same version is priced in `shared` mode
- **THEN** the pricing lists 8 hinge cup borings with no fee
