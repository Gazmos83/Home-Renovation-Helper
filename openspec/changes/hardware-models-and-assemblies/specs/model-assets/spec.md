## ADDED Requirements

### Requirement: A model can be assigned to a hardware key
The owner SHALL be able to assign a `ready` model to one hardware key from the model library, and clear that assignment, through owner-gated routes. A key SHALL hold at most one model; a model may serve several keys. The assignment SHALL be refused, with nothing stored, in each of these cases:
- the model is not `ready`;
- the key has no catalog entry;
- the model's stated size differs from the catalog shape's size, in any dimension, by more than the catalog's tolerance. The refusal names both sizes.

The page SHALL state the authoring convention: +Z up, with the mounting face towards +Y.

#### Scenario: Assigned
- **WHEN** the owner assigns the `ready` 32 × 28 × 30 mm `brass-knob` model to `handle-knob-brass`, whose catalog knob is 30 × 25 × 30 mm
- **THEN** the assignment is stored and listed beside the model

#### Scenario: Size too far off
- **WHEN** the owner assigns an 800 × 700 × 900 mm armchair to `handle-knob-brass`
- **THEN** it is refused naming both sizes, and nothing is stored

#### Scenario: Not ready
- **WHEN** the model is still `checking`
- **THEN** the assignment is refused saying the model is not ready yet
