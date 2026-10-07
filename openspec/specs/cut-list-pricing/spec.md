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
A part, hardware line or band whose material has no price-list entry, a part too large for any sheet, or a cut whose service cannot be determined SHALL be listed by name, counted, and SHALL mark the pricing incomplete; no price SHALL be invented for it.

#### Scenario: Unknown hardware
- **WHEN** a hardware line has no entry
- **THEN** the pricing is incomplete and lists that line as unpriced by its id

### Requirement: Cuts are classified against the home store
Each cut SHALL be classified as `covered`, `custom` or `undetermined` against the configured home toom store's captured cut services and the owner's restrictions for that store, the owner's restriction outranking the captured service; a part whose notes name machining (holes, cut-outs, mitres, grommets) SHALL be marked for review. The cut charge SHALL follow the chosen mode: `shared` (no per-cut fee) or `per_cut` (the straight-cut price times the cut count); with no mode chosen the pricing SHALL say the choice is open.

#### Scenario: Restriction outranks the service
- **WHEN** the store's captured services include straight cuts but the owner records that this store does not cut panels thicker than 25 mm
- **THEN** a 27 mm worktop cut is `custom`

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
