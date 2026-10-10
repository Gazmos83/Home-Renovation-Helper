## MODIFIED Requirements

### Requirement: Shelf-pin holes are drilled in dividers too
When a module with adjustable shelves has dividers, the shelf-pin calculation SHALL list:
- one entry for the sides, on the inner face, as before;
- one entry for each divider row, on both faces of each divider in that row.

The entries SHALL use the same columns. A divider's hole row SHALL be the data sheet's first hole, last hole and pitch applied to the divider's own length, measured from its bottom end, which sits on the top face of the board it stands on (the bottom panel for a full-height divider, which gives the same holes as before). A divider whose span holds no adjustable shelf SHALL have no shelf-pin entry. Fixing a shelf (stating it fixed in `shelf_kinds`) SHALL NOT change the side boards' hole row; only the pin count follows the adjustable shelves. The shelf-pin hole count SHALL include the holes of every divider face. When the holes are blank or given as a rule in words, no entry SHALL have a count, as before. A module without dividers SHALL give the same entry as before, and a module whose dividers all run full height SHALL give the same entries as before.

#### Scenario: Holes on a divider listed
- **WHEN** a module has one divider and two adjustable shelves, and the shelf-pin data sheet gives every value with 10 hole heights
- **THEN** the drilling list holds the side entry with 40 holes and a divider entry with 40 holes on both faces, each with its source

#### Scenario: No dividers, unchanged
- **WHEN** a module without dividers has adjustable shelves
- **THEN** its shelf-pin entry equals the one given before this change

#### Scenario: Partial divider drills only its span
- **WHEN** a module has a divider from its top fixed shelf to the top panel, and one adjustable shelf above that fixed shelf and one below it
- **THEN** the divider entry lists the hole row from the data sheet's first hole to its last hole along the divider's own length, measured from its bottom end on the fixed shelf's top face

#### Scenario: Divider with no adjustable shelf in its span
- **WHEN** a module's only divider runs between two fixed shelves with no adjustable shelf between them
- **THEN** the drilling list holds no divider shelf-pin entry for it

#### Scenario: Fixing a shelf keeps the side holes
- **WHEN** the top of four adjustable shelves is fixed through `shelf_kinds`
- **THEN** the side entries list the same holes as before, and the shelf-pin quantity counts 3 adjustable shelves
