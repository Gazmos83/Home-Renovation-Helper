## ADDED Requirements

### Requirement: Hanging-rail supports are counted by a cited rule
The closed set of piece checks SHALL include `rail_support_count_for_length`, a count check that reads a table of rows, each with a longest rail length and a number of supports, plus a count for longer rails. A rail SHALL take the first row whose length is at least its cut length, and the `beyond` count past the last row. The check gives the rail calculator its support count and judges nothing, so it never raises a warning. At most one rule SHALL name it, and when a version is built its frozen hardware inputs SHALL keep that rule, as they keep the other count rules. No rule SHALL ship for it until the owner adds a note with the clause to cite.

#### Scenario: Supports from the rule
- **WHEN** the inputs hold a rail-support rule giving 2 up to 1000 mm and 3 beyond, and a rail is cut 1196 mm
- **THEN** the support line counts 3 for that rail and its note names the rule and its source

#### Scenario: No rule, end supports only
- **WHEN** no rail-support rule is in force
- **THEN** each rail counts 2 supports and the note says no centre-support rule applies

#### Scenario: Second rail-support rule refused
- **WHEN** the rules table holds two rules naming `rail_support_count_for_length`
- **THEN** loading fails naming both rules
