## ADDED Requirements

### Requirement: Shelf-pin holes are drilled in dividers too
When a module with adjustable shelves has dividers, the shelf-pin calculation SHALL list:
- one entry for the sides, on the inner face, as before;
- one entry for the module's divider row, on both faces of each divider.

Both entries SHALL use the same columns and hole heights. A divider's hole heights SHALL be measured from its bottom end, which sits on the top face of the bottom panel. The shelf-pin hole count SHALL include the holes of every divider face. When the holes are blank or given as a rule in words, neither entry SHALL have a count, as before. A module without dividers SHALL give the same entry as before.

#### Scenario: Holes on a divider listed
- **WHEN** a module has one divider and two adjustable shelves, and the shelf-pin data sheet gives every value with 10 hole heights
- **THEN** the drilling list holds the side entry with 40 holes and a divider entry with 40 holes on both faces, each with its source

#### Scenario: No dividers, unchanged
- **WHEN** a module without dividers has adjustable shelves
- **THEN** its shelf-pin entry equals the one given before this change
