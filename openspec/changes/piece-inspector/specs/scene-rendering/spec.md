## MODIFIED Requirements

### Requirement: A turntable of the piece
A turntable at a tier SHALL:
- render exactly the tier's frame count from cameras spaced evenly around the build's centre, at the tier's resolution and engine;
- publish the frames as `frames/frame_000.png` … `frames/frame_<N-1>.png`, all at once;
- write `viewer.html` beside them with the frame count filled in;
- record tier, frame count, resolution, engine and each frame's camera position in `scene.json`.

A previous turntable of the version SHALL be replaced whole.

A turntable of a piece's own `model.blend` SHALL show the version's dimension lines, at every tier, with each figure turned to face the camera in every frame. The build's centre that the cameras orbit SHALL be taken from the piece alone, not from the dimension lines. A version whose `model.blend` has no dimension lines SHALL render as before.

#### Scenario: Draft turntable
- **WHEN** a `draft` turntable is requested for a built version
- **THEN** `frames/` holds exactly `frame_000.png` … `frame_011.png`, each 600 × 600, and `viewer.html` names 12 frames

#### Scenario: Dimension lines turn with the camera
- **WHEN** a `draft` turntable is rendered of a version built with dimension lines
- **THEN** every frame shows the width, height and depth lines, and each figure faces the camera in that frame

#### Scenario: Older version
- **WHEN** a turntable is rendered of a version built before dimension lines existed
- **THEN** it renders and publishes as before, without dimension lines

#### Scenario: Viewer works offline
- **WHEN** `viewer.html` is opened beside its frames
- **THEN** dragging or scrolling cycles through the frames in order and wraps at both ends

## ADDED Requirements

### Requirement: Dimension lines show only in a piece's own turntable
The dimension objects SHALL be hidden in every other render:
- a still;
- a room still or turntable;
- a detail-pass still or turntable;
- a shell or composition render.

They SHALL be hidden whether the render runs on the laptop or on the render server.

#### Scenario: Still stays clean
- **WHEN** a still is rendered of a version built with dimension lines
- **THEN** the still shows no dimension line

#### Scenario: Detail turntable stays clean
- **WHEN** a `final` detail turntable is rendered from a detail copy of a version with dimension lines
- **THEN** no frame shows a dimension line

#### Scenario: Remote final turntable
- **WHEN** a `final` turntable of a piece runs on the render server
- **THEN** its frames show the dimension lines, the same as on the laptop
