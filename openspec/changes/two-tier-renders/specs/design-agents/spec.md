## MODIFIED Requirements

### Requirement: The Builder builds and renders only through the guard
`blender_build` SHALL build a version that has not succeeded yet, wait for it within the Blender timeout, and report the outcome with the screenshot route; a version already built SHALL be reported as such without rebuilding. `render_turntable` SHALL require a tier, `draft` or `final`, and SHALL refuse raw frame, resolution or engine values by name. It SHALL render a still or a turntable of a version alone or placed with a `room_fit` placement, except that a `draft` of a piece version alone SHALL be a turntable: a `draft` still of a piece version alone SHALL be refused, saying a draft of a piece is a turntable. For `draft` it SHALL start the run and report the estimate; for `final` it SHALL pause with the estimate and run only on `yes`. When a render starts, the reply SHALL give the estimate and SHALL NOT give a viewer route: for a piece version it SHALL say that a Review button appears in this chat when the render finishes, and for a shell or composition that a notice appears in this chat. The Builder SHALL never write or run Blender Python.

#### Scenario: Draft turntable
- **WHEN** the owner asks for a draft turntable of a built piece
- **THEN** the run is started at tier `draft` and the reply gives the estimate in plain terms and says a Review button appears in this chat when it finishes, with no viewer route

#### Scenario: Draft still of a piece refused
- **WHEN** the Builder's call asks for a `draft` still of a built piece on its own
- **THEN** it is refused saying a draft of a piece is a turntable, and no process starts

#### Scenario: Draft still of a placed piece
- **WHEN** the Builder's call asks for a `draft` still of a built piece placed with a `room_fit` placement
- **THEN** the run is started at tier `draft` and the reply gives the estimate

#### Scenario: Final paused
- **WHEN** the owner asks for a final render
- **THEN** the reply carries a pending confirmation with the estimate and nothing has started

#### Scenario: Raw frames refused
- **WHEN** the Builder's call carries `frames: 100`
- **THEN** it is refused naming `frames` and no process starts
