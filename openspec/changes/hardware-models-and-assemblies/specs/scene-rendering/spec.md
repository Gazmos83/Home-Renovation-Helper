## ADDED Requirements

### Requirement: A render names the pose it shows
A still or turntable of a piece MAY name a pose from its version's `spec.json` `poses`; without one, the stored pose is rendered. A pose not in that list SHALL be refused by name before any estimate. The render SHALL apply the pose in memory to the opened `model.blend` and save nothing. Each pose rendered SHALL be its own render under the render guard: its own tier, estimate and ticket, with the typed "yes" for `final`. The published render SHALL record its pose.

#### Scenario: Open pose draft
- **WHEN** the owner asks for a draft turntable of the fold bed unfolded
- **THEN** one draft is estimated and run with the bed open, and its record names pose `open`

#### Scenario: Unknown pose
- **WHEN** a render names pose `half-open`
- **THEN** it is refused naming `half-open` and the version's poses, and nothing is estimated or run
