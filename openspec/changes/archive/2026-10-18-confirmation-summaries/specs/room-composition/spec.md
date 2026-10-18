## ADDED Requirements

### Requirement: A composition proposal lists its calculations as a table
A proposed composition version SHALL carry, beside its summary, a table with one row per item, in the document's order. Each row SHALL give the item's name (a piece as its name and version, a model or stand-in as its name), its kind (piece, model or stand-in), its size W × D × H in millimetres, its placement in plain words (the wall and offset, or "free" with the rotation), its resolved centre x and y in millimetres, and, for a ceiling-layer item, how high its lowest point hangs. The values SHALL be the ones the placement checks computed, not recomputed for display. A composition with no items SHALL carry an empty table. The table SHALL be shown wherever the confirmation is shown, and SHALL NOT be sent to any model.

#### Scenario: Two items placed
- **WHEN** the Designer proposes `Wohnen` with `sofa` against wall 2 at 400 mm and `lamp` free at (1800, 2100) mm turned 0°
- **THEN** the confirmation's table has two rows, the sofa's giving "wall 2, 400 mm" with its resolved centre, and the lamp's giving "free, 0°" with centre 1800, 2100

#### Scenario: Room only
- **WHEN** the Designer proposes `Wohnen` with no items
- **THEN** the confirmation carries an empty table and its summary says the room only
