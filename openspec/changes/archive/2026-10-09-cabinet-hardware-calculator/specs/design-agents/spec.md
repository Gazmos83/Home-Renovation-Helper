## MODIFIED Requirements

### Requirement: The cut list is derived without rendering
`cut_list` SHALL return a version's derived parts (id, qty, length, width, thickness, material) and hardware lines from its stored document and its saved hardware inputs, with totals, and its drilling list per part with the drilling-work counts, without starting any Blender process. A ranged position SHALL be reported as its range and a position given as a rule as its words, never as a single number. When the drilling list is incomplete, `cut_list` SHALL say so and name every missing value; for a version with no saved inputs it SHALL say that drilling was not calculated.

#### Scenario: Parts listed
- **WHEN** the Designer calls `cut_list` for `hall-bench` version 1
- **THEN** the result lists every derived part with its dimensions and no process is started

#### Scenario: Drilling incomplete
- **WHEN** the Designer calls `cut_list` for a version whose hinge data sheet lacks the cup edge distance
- **THEN** the result lists the drilling positions it has, says the drilling list is incomplete, and names "cup edge distance"
