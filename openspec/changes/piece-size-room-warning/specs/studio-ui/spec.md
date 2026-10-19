## ADDED Requirements

### Requirement: The inspector shows a too-big warning
The inspector SHALL show, for the version it displays, the same size warnings the build notice carries (taller than the room's ceiling, wider than its longest wall), as a visible warning line near the version's title. A version with no warning SHALL show none. The warning SHALL NOT hide or disable the inspector's approve, render or download actions.

#### Scenario: Warning in the inspector
- **WHEN** the owner inspects `hochschrank` v2, which is 2600 mm tall in a room with a 2500 mm ceiling
- **THEN** the inspector shows "Too big for Wohnen: 2600 mm tall, the ceiling is 2500 mm." and the Approve action is still offered

### Requirement: The Brief form marks the height limit optional
The Brief form SHALL label the height limit "Highest the piece may be (mm, optional)" and SHALL save the brief with the field left empty. A value that is filled in SHALL still be a number above 0.

#### Scenario: Saved empty
- **WHEN** the owner clears the height limit and saves the brief
- **THEN** the brief is saved with no limit and no error is shown
