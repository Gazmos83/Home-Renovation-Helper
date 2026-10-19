## MODIFIED Requirements

### Requirement: The Builder builds and renders only through the guard
`blender_build` SHALL build a version that has not succeeded yet, wait for it within the Blender timeout, and report the outcome with the screenshot route; a version already built SHALL be reported as such without rebuilding. `render_turntable` SHALL require a tier, `draft` or `final`, and SHALL refuse raw frame, resolution or engine values by name. It SHALL render a still or a turntable of a composed room or an apartment shell only. A piece version, on its own or placed in a room, SHALL NOT be rendered: such a call SHALL be refused in plain words, saying renders are made of rooms and offering to compose the room with the piece and render the room. For `draft` it SHALL start the run and report the estimate; for `final` it SHALL pause with the estimate and run only on `yes`. When a render starts, the reply SHALL give the estimate and SHALL NOT give a viewer route, and SHALL say that a notice appears in this chat when it finishes. The Builder SHALL never write or run Blender Python.

#### Scenario: Draft turntable
- **WHEN** the owner asks for a draft turntable of the composed room `Wohnen`
- **THEN** the run is started at tier `draft` and the reply gives the estimate in plain terms and says a notice appears in this chat when it finishes, with no viewer route

#### Scenario: Draft still of a piece refused
- **WHEN** the Builder's call asks for a render of a built piece on its own
- **THEN** it is refused saying renders are made of rooms, and no process starts

#### Scenario: Draft still of a placed piece
- **WHEN** the Builder's call asks for a still of a built piece placed in the conversation's room
- **THEN** it is refused saying renders are made of rooms and offering to compose and render the room, and no process starts

#### Scenario: Final paused
- **WHEN** the owner asks for a final render of a composed room
- **THEN** the reply carries a pending confirmation with the estimate and nothing has started

#### Scenario: Raw frames refused
- **WHEN** the Builder's call carries `frames: 100`
- **THEN** it is refused naming `frames` and no process starts
