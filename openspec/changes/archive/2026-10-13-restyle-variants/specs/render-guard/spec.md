## MODIFIED Requirements

### Requirement: A render names its source and a detail render is final only
Every render request SHALL render the version's built model, its detail-pass copy, or a restyle of the built model; the built model is the default. A request for the detail copy SHALL be refused unless:
- the tier is `final`; otherwise the refusal says a detail render is final only and progress is checked with a screenshot;
- the detail copy exists;
- the render is of the piece alone, not placed in a room.

A request for a restyle SHALL be refused at tier `final`, saying a restyle is a concept picture, and SHALL name the one variant it is for.

A guard authorisation SHALL match the source it was issued for. An authorisation for the built model SHALL NOT launch a render of the detail copy or a restyle, nor the reverse, and a restyle authorisation SHALL NOT launch any variant but the one it was issued for. A detail render SHALL follow the same estimate, approval, record and one-process rules as any `final` render. A restyle SHALL follow the same estimate, record and one-process rules as any `draft` or `preview` render.

#### Scenario: Draft detail render refused
- **WHEN** a detail render is requested at tier `draft`
- **THEN** it is refused saying a detail render is final only, and no process starts

#### Scenario: Final detail render approved
- **WHEN** a detail turntable is requested at tier `final` and the owner answers `yes` to the estimate
- **THEN** one render of `detail/detail.blend` runs with 36 frames at 1500 × 1500 on Cycles

#### Scenario: Ticket for the wrong source
- **WHEN** an authorisation issued for the built model is presented to launch a detail render of the same version
- **THEN** the launch is refused and no process starts

#### Scenario: Restyle at final refused
- **WHEN** a restyle is requested at tier `final`
- **THEN** it is refused saying a restyle is a concept picture, and no process starts

#### Scenario: Ticket for a restyle used for another variant
- **WHEN** an authorisation issued for the variant `walnut` is presented to launch `sage-green`
- **THEN** the launch is refused and no process starts
