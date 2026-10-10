## MODIFIED Requirements

### Requirement: Cuts are classified against the home store
Each cut SHALL be classified as `covered`, `custom` or `undetermined` against the configured home toom store's captured cut services and the owner's restrictions for that store, the owner's restriction outranking the captured service; a part whose notes name machining (holes, cut-outs, mitres, grommets) SHALL be marked for review. The cut charge SHALL follow the chosen mode: `shared` (no per-cut fee) or `per_cut` (the straight-cut price times the cut count); with no mode chosen the pricing SHALL say the choice is open.

#### Scenario: Restriction outranks the service
- **WHEN** the store's captured services include straight cuts but the owner records that this store does not cut panels thicker than 25 mm
- **THEN** a 27 mm worktop cut is `custom`

#### Scenario: Derived mitre notes marked for review
- **WHEN** a version whose cut list includes a side-upper row with notes naming a 26° mitre is priced
- **THEN** that row is marked for review
