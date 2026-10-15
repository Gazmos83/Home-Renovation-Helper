## MODIFIED Requirements

### Requirement: A render names its source and a detail render is final only
Every render request SHALL render the version's built model, its detail-pass copy, or a restyle of the built model; the built model is the default. A request for the detail copy SHALL be refused unless:
- the tier is `final`; otherwise the refusal says a detail render is final only and progress is checked with a screenshot;
- the detail copy exists;
- the render is of the piece alone, not placed in a room.

A detail still or turntable MAY run on the laptop or on the render server, wherever finals run. A detail render SHALL be a still unless a turntable is asked for.

A request for a restyle SHALL be refused at tier `final`, saying a restyle is a concept picture. It SHALL be refused when it is not a turntable, saying a restyle is a draft turntable. It SHALL name the one variant it is for.

A guard authorisation SHALL match the source it was issued for. An authorisation for the built model SHALL NOT launch a render of the detail copy or a restyle, nor the reverse, and a restyle authorisation SHALL NOT launch any variant but the one it was issued for. A detail render SHALL follow the same estimate, approval, record and one-process rules as any `final` render. A restyle SHALL follow the same estimate, record and one-process rules as any `draft` render.

#### Scenario: Draft detail render refused
- **WHEN** a detail render is requested at tier `draft`
- **THEN** it is refused saying a detail render is final only, and no process starts

#### Scenario: Final detail render approved
- **WHEN** finals run on the laptop, a detail still is requested at tier `final` and the owner answers `yes` to the estimate
- **THEN** one render of `detail/detail.blend` runs on the laptop: one frame at 1500 × 1500 on Cycles

#### Scenario: Local detail turntable refused
- **WHEN** finals run on the laptop and a detail turntable is requested at tier `final`
- **THEN** it is not refused: the approval shows the estimate with the long-render and laptop-busy warnings, nothing starts before `yes`, and on `yes` one render of `detail/detail.blend` runs on the laptop with 36 frames at 1500 × 1500 on Cycles

#### Scenario: Detail turntable on the render server
- **WHEN** finals go to the render server, a detail turntable is requested at tier `final` and the owner answers `yes` to the estimate
- **THEN** one render of `detail/detail.blend` runs on the render server with 36 frames at 1500 × 1500 on Cycles

#### Scenario: Ticket for the wrong source
- **WHEN** an authorisation issued for the built model is presented to launch a detail render of the same version
- **THEN** the launch is refused and no process starts

#### Scenario: Restyle at final refused
- **WHEN** a restyle is requested at tier `final`
- **THEN** it is refused saying a restyle is a concept picture, and no process starts

#### Scenario: Restyle still refused
- **WHEN** a restyle still is requested at tier `draft`
- **THEN** it is refused saying a restyle is a draft turntable, and no process starts

#### Scenario: Ticket for a restyle used for another variant
- **WHEN** an authorisation issued for the variant `walnut` is presented to launch `sage-green`
- **THEN** the launch is refused and no process starts

## ADDED Requirements

### Requirement: A long render is approved with its time and the laptop's wait
When a render that needs approval is quoted above 20 minutes, its approval SHALL carry a long-render warning, wherever the approval is asked: in a conversation, at a graph interrupt, or over HTTP. The warning SHALL state:
- the estimate in hours and minutes;
- that the estimate is rough until the first `final` calibrates the Cycles multiplier;
- that heavy lighting can make it longer.

For a detail turntable, the warning SHALL also say that a single detail still (with its estimate) is much faster, and so is the render server when one is configured. When the render would run on the laptop, the approval SHALL also say that it holds the laptop's one Blender process for that time, so builds, drafts and the live detail pass wait behind it. A render quoted at 20 minutes or less SHALL be approved as before, without these warnings.

#### Scenario: Local detail turntable warned
- **WHEN** the benchmark is 5.031 seconds per megapixel, the Cycles multiplier is 30, finals run on the laptop and a detail turntable is requested
- **THEN** the approval states about 3 h 24 min, that it is rough until the first final calibrates it and lighting can make it longer, that a detail still takes about 6 minutes, and that builds, drafts and the live detail pass wait behind it

#### Scenario: Short final not warned
- **WHEN** a `final` still is quoted at 6 minutes
- **THEN** its approval shows the estimate with no long-render or laptop-busy warning

#### Scenario: Remote long render
- **WHEN** a `final` turntable quoted above 20 minutes is asked to run on the render server
- **THEN** its approval carries the long-render warning and no laptop-busy warning

### Requirement: A final runs for up to six hours
A `final` render SHALL be stopped when it runs longer than 36 times the Blender timeout (6 hours at the 600-second default), on the laptop and on the render server, and SHALL fail stating the timeout. A `draft` keeps its own limit.

#### Scenario: Shipped final limit
- **WHEN** the service starts with the shipped render configuration and the default Blender timeout
- **THEN** a `final` render is allowed 21 600 seconds before it is stopped
