## MODIFIED Requirements

### Requirement: A composition renders only through the guard
A still or turntable of a composition version SHALL go through the render guard exactly as a piece or a shell does: a tier is required, raw frame, resolution and engine values are refused by name, the estimate is stated before the run, and `final` runs only after the owner's `yes`. An empty room composition SHALL follow the same rules. Output SHALL be published atomically in the composition version's folder, in the same `still.png`, `frames/`, `viewer.html` and `scene.json` layout. For a turntable, walls between the camera and the room SHALL be hidden per frame. A room scope SHALL be the default. An apartment scope SHALL be rendered only when the composition's scope is an apartment.

#### Scenario: Draft turntable of a room
- **WHEN** a `draft` turntable of `Wohnen` v2 is requested
- **THEN** 12 frames at 800 × 800 on Eevee are published under that version, and `scene.json` records the tier and the composition document

#### Scenario: Draft still of an empty room
- **WHEN** a `draft` still of the empty `Hall` v1 is requested
- **THEN** the estimate is stated, an 800 × 800 Eevee still of the room alone is published under that version, and `scene.json` records the tier and an empty item list

#### Scenario: Final needs yes
- **WHEN** a `final` still of a composition is requested
- **THEN** a confirmation with the estimate is pending and nothing has started

#### Scenario: Raw resolution refused
- **WHEN** the render request carries `resolution: 4000`
- **THEN** it is refused naming `resolution` and no process starts
