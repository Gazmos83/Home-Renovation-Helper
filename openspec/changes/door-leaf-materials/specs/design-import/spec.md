## ADDED Requirements

### Requirement: The import template names per-door materials
The import template's guide SHALL hold one line saying that a door entry's `leaf_materials` maps door numbers (from 1 on the left) to material slots, so that one door of a pair can have its own colour while the doors stay side by side. Each guide line SHALL stay within the template's line limit. A design file with `leaf_materials` SHALL be imported, previewed and refused by the same rules as one written in the conversation.

#### Scenario: Guide line present
- **WHEN** the owner downloads the import template
- **THEN** its guide holds a line naming `leaf_materials` and door numbers from 1 on the left

#### Scenario: Imported design with a black right door
- **WHEN** an attached design has one entry of two doors with `leaf_materials` {"2": "black_paint"}
- **THEN** the import preview names "door 2 black_paint", and on yes the new version's cut list holds `<entry row>-1` and `<entry row>-2`
