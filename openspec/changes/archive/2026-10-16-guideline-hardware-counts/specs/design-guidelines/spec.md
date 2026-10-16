## ADDED Requirements

### Requirement: Shelf pins and hinges are counted by cited rules
The closed set of piece checks SHALL include two count checks:
- **Shelf-pin count.** A table of rows, each giving the widest shelf board and the pins per shelf, plus a count for boards wider than the last row.
- **Hinge count.** A table of rows, each giving the tallest door and the hinges per door, plus a count for doors taller than the last row.

A board or door SHALL take the first row whose limit is at least its own width or height. A board or door beyond the last row SHALL take the beyond count. Every count SHALL be a whole number from 1 to 64 and SHALL NOT be a range. The rows SHALL be given in rising order, and no two rows SHALL share a limit. A table that breaks either rule SHALL be refused, naming the rule and its parameters.

A spec states no pin or hinge count, so neither check SHALL judge a spec or raise a finding. Their only use is to give the cut list and the drilling list their count, as set out in the furniture-packages and hardware-drilling specs. At most one rule SHALL name each count check. A second rule naming the same check SHALL fail startup, or be refused on the developer panel, naming both rules, as for the bracket checks.

The checked-in table SHALL ship two rules at severity `warn`, each citing an owner note:
- `shelf-pin-count` cites the note "Shelf Pin Count" (`owner:7cf8c9ef-e98f-4d3d-af6c-f0384a17ffdd`): 4 pins per shelf for boards up to 914 mm wide (36 in, rounded down to a whole millimetre), and 5 beyond. Where the note says "5 or more", the minimum is taken.
- `hinge-count` cites the note "Hinge Quantity per Door" (`owner:a8147011-0f73-4e5e-a5f2-e3a9f8fd9852`): 2 hinges up to 1016 mm, 3 up to 1524 mm, 4 up to 2032 mm, and 5 beyond.

Each rule's quote SHALL be the note's clause it is taken from.

#### Scenario: Shipped rules load
- **WHEN** the service starts with the checked-in table
- **THEN** `shelf-pin-count` and `hinge-count` are in force, and the developer panel lists them with their checks, parameters, severity `warn` and quoted owner notes

#### Scenario: Second pin-count rule refused
- **WHEN** the developer adds a second rule naming the shelf-pin count check
- **THEN** it is refused naming both rules, and the rules in force are unchanged

#### Scenario: Range for a count refused
- **WHEN** a hinge-count rule gives "4–5" hinges for a row
- **THEN** it is refused naming the rule and its parameters

#### Scenario: No finding from a count rule
- **WHEN** the Designer previews a piece with two 1200 mm doors and three adjustable shelves
- **THEN** the preview shows no finding from either count rule
