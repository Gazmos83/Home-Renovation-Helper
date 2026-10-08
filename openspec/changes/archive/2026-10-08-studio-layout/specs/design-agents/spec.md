## MODIFIED Requirements

### Requirement: The Builder builds and renders only through the guard
`blender_build` SHALL build a version that has not succeeded yet, wait for it within the Blender timeout, and report the outcome with the screenshot route; a version already built SHALL be reported as such without rebuilding. `render_turntable` SHALL require a tier, SHALL refuse raw frame, resolution or engine values by name, SHALL render a still or a turntable of a version alone or placed with a `room_fit` placement, and SHALL start the run and report the estimate for `draft` and `preview`; for `final` it SHALL pause with the estimate and run only on `yes`. When a render starts, the reply SHALL give the estimate and SHALL NOT give a viewer route: for a piece version it SHALL say that a Review button appears in this chat when the render finishes, and for a shell or composition that a notice appears in this chat. The Builder SHALL never write or run Blender Python.

#### Scenario: Draft turntable
- **WHEN** the owner asks for a draft turntable of a built piece
- **THEN** the run is started at tier `draft` and the reply gives the estimate in plain terms and says a Review button appears in this chat when it finishes, with no viewer route

#### Scenario: Final paused
- **WHEN** the owner asks for a final render
- **THEN** the reply carries a pending confirmation with the estimate and nothing has started

#### Scenario: Raw frames refused
- **WHEN** the Builder's call carries `frames: 100`
- **THEN** it is refused naming `frames` and no process starts

### Requirement: The Builder renders a composition through the guard
`render_turntable` SHALL accept exactly one target: a piece, a shell, or a composition (its scope name and, optionally, a version, the latest by default). A composition target SHALL follow the same tier, refusal, estimate and `final` approval rules as the other targets. It SHALL refuse a composition version whose build has not succeeded, saying it must be built first. When the composition has a placed version that is no longer approved, the reply SHALL say so. A composition with a built version SHALL give the Builder something to work on, in the same way a built piece or shell does.

#### Scenario: Draft of a room
- **WHEN** the owner asks for a draft turntable of `Wohnen`
- **THEN** the run starts at tier `draft` on the latest built version, and the reply gives the estimate and says a notice appears in this chat when it finishes, with no viewer route

#### Scenario: Two targets
- **WHEN** a call names both a piece and a composition
- **THEN** it is refused saying to name exactly one target

### Requirement: No specialist promises to report back after the turn
A turn SHALL end with its reply, and no specialist SHALL message the owner afterwards. No specialist's instructions SHALL let it promise to tell the owner later when a build, a render or a review finishes. The only message after a turn SHALL be the render notice that code posts when a render started in the conversation finishes or fails; it is never written by a model. The Builder and the Designer SHALL say that a started build's status shows in the conversation's Project panel and can be asked for in a later message.

#### Scenario: Owner asks to be told when the build is done
- **WHEN** a build has started and the owner asks "Will you tell me when the build is complete?"
- **THEN** the reply says the Project panel shows the build's status and that the owner can ask again, and it does not promise a later message

#### Scenario: Render notice is posted by code
- **WHEN** a draft turntable started in the conversation finishes after the turn has ended
- **THEN** a render notice appears in the conversation, posted by code, and no specialist runs or writes a message
