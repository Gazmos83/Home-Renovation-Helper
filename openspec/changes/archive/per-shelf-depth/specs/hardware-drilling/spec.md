## ADDED Requirements

### Requirement: An adjustable shelf with a custom depth must cover the pin columns
Shelf-pin hole columns SHALL stay on each side's inner face at the data sheet's front setback from the front edge and rear setback from the rear edge, as today. They SHALL NOT move with a shelf's custom depth.

When a module states `shelf_depths_mm` for an adjustable shelf, and the shelf-pin data sheet gives both setbacks as exact millimetre values, that shelf's placed depth SHALL cover both columns. A depth that leaves either column outside the board SHALL be refused, naming `shelf_depths_mm` and the shelf number. When either setback is missing, ranged, or given as a rule in words, no depth-coverage check SHALL run for that module.

A module without `shelf_depths_mm`, and a module whose adjustable shelves all use the back-reduced depth, SHALL give the same drilling list as before.

#### Scenario: Shallower adjustable shelf still covers both columns
- **WHEN** a 400 mm deep module with no back has one adjustable shelf, exact front and rear setbacks of 37 mm, `shelf_depths_mm` [370] and align `"back"`
- **THEN** the document is accepted (the board runs from 30 mm to 400 mm from the front, covering both columns) and the side pin columns stay at 37 mm from each edge

#### Scenario: Too-shallow adjustable shelf refused
- **WHEN** a 400 mm deep module with no back has one adjustable shelf, exact front and rear setbacks of 37 mm, `shelf_depths_mm` [300] and align `"back"`
- **THEN** it is refused, naming `shelf_depths_mm` and shelf 1 (the board starts at 100 mm from the front, past the front column at 37 mm)

#### Scenario: Full-depth adjustable shelves unchanged
- **WHEN** a module has two adjustable shelves and no `shelf_depths_mm`, and the shelf-pin data sheet gives every value
- **THEN** its shelf-pin drilling entry equals the one given before this change
