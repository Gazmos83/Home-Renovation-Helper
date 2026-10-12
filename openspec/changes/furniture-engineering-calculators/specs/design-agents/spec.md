## ADDED Requirements

### Requirement: Engineering specialists confirm inputs and relay deterministic reports
Designer and Researcher SHALL be able to propose owner-confirmed assessment inputs and request bounded calculations through declared tools. They SHALL relay application-generated results and qualifications without model arithmetic, altered limits or inferred engineering approval. A disabled/unreviewed/unavailable method SHALL be stated as unavailable/NOT VERIFIED. A calculation SHALL NOT start Blender, change a spec, approve a piece or authorise installation. An ordinary dimensional revision SHALL use the existing confirmation workflow and invalidate any assessment shown for changed geometry.

#### Scenario: Tool returns unresolved fixing
- **WHEN** the calculator reports bending passing and anchorage NOT VERIFIED
- **THEN** the reply retains both qualifications and does not say the piece is safe to build

#### Scenario: Calculation plugin off
- **WHEN** the calculation tool is disabled and the owner asks for a new capacity result
- **THEN** the specialist reports calculation unavailable rather than reproducing remembered arithmetic

#### Scenario: Dimensional change
- **WHEN** the owner confirms a wider shelf
- **THEN** normal revision proceeds and the old assessment is not presented as current for the new geometry
