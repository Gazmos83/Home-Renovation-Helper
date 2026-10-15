## RENAMED Requirements

- FROM: `### Requirement: A restyle still renders an in-memory override of the built model`
- TO: `### Requirement: A restyle turntable renders an in-memory override of the built model`

## MODIFIED Requirements

### Requirement: A still of the piece
A still at a tier SHALL render one frame from the package's isometric studio camera at the tier's resolution and engine and publish it as `still.png` in the version folder, replacing any earlier still, and SHALL record the tier, resolution and engine used in `scene.json`.

#### Scenario: Draft still
- **WHEN** a `draft` still is requested for a built version
- **THEN** `still.png` exists at 800 × 800, and `scene.json` records tier `draft` and engine Eevee

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
- **THEN** `frames/` holds exactly `frame_000.png` … `frame_011.png`, each 800 × 800, and `viewer.html` names 12 frames

#### Scenario: Dimension lines turn with the camera
- **WHEN** a `draft` turntable is rendered of a version built with dimension lines
- **THEN** every frame shows the width, height and depth lines, and each figure faces the camera in that frame

#### Scenario: Older version
- **WHEN** a turntable is rendered of a version built before dimension lines existed
- **THEN** it renders and publishes as before, without dimension lines

#### Scenario: Viewer works offline
- **WHEN** `viewer.html` is opened beside its frames
- **THEN** dragging or scrolling cycles through the frames in order and wraps at both ends

### Requirement: A room still or turntable
A room render at a tier SHALL build the room shell and furnishings, import the version's model at the placement, and render a still or turntable at the tier's frame count, resolution and engine into the version's `room/` folder with the same `still.png`, `frames/`, `viewer.html` and `scene.json` layout, where `scene.json` also carries the normalised room document. For a turntable the walls between the camera and the room SHALL be hidden per frame, as in the predecessor.

#### Scenario: Room draft turntable
- **WHEN** a `draft` room turntable is requested with the rectangle room fixture
- **THEN** `room/frames/` holds exactly 12 frames at 800 × 800 and `room/scene.json` records the room document, the placement and tier `draft`

### Requirement: A detail render publishes beside the version
A detail still or turntable SHALL render the version's `detail/detail.blend` with the same cameras as the built model's still or turntable. A detail turntable SHALL be rendered only on the render server; on the laptop a detail render is a still. It SHALL publish into the version's `detail/` folder with the same `still.png`, `frames/`, `viewer.html` and `scene.json` layout, verification and atomic publish, and `scene.json` SHALL record source `detail`. Before the render starts, the live Blender's open detail file SHALL be saved when Blender is reachable. When Blender is not reachable, the copy on disk SHALL be rendered as it is. A detail render SHALL NOT replace or alter the version's own `still.png`, `frames/` or `viewer.html`.

#### Scenario: Final detail turntable published
- **WHEN** an approved `final` detail turntable completes on the render server
- **THEN** `detail/frames/` holds exactly `frame_000.png` … `frame_035.png` at 1500 × 1500, `detail/viewer.html` names 36 frames, and the version's own `frames/` is unchanged

#### Scenario: Final detail still on the laptop
- **WHEN** an approved `final` detail still completes on the laptop
- **THEN** `detail/still.png` exists at 1500 × 1500, `detail/scene.json` records source `detail`, and the version's own `still.png` is unchanged

#### Scenario: Live Blender closed before the render
- **WHEN** a `final` detail still is approved while the live Blender is closed
- **THEN** the render uses `detail/detail.blend` as saved on disk

### Requirement: A restyle turntable renders an in-memory override of the built model
A restyle SHALL open the version's built `model.blend` (or, for a composition, rebuild the room from its stored document), apply the look or style in memory, render a turntable at the tier's frame count, resolution and engine with the same cameras as the version's own turntable, and close without saving. It SHALL publish into `variants/<variant-id>/` of the version, and SHALL NOT replace or alter the version's own `still.png`, `frames/`, `viewer.html` or `model.blend`. It SHALL be refused with a stated reason when the version has not succeeded or its `model.blend` is missing.

#### Scenario: Built model untouched
- **WHEN** a draft restyle turntable completes
- **THEN** `model.blend` is byte-identical to before, and the version's own `still.png` and `frames/` are unchanged

#### Scenario: Composition restyle turntable
- **WHEN** a draft restyle of the composition `Wohnen` v2 with one style completes
- **THEN** its variant folder holds 12 frames at 800 × 800, with walls between the camera and the room hidden per frame, and the composition version's own files are unchanged

#### Scenario: Version not built
- **WHEN** a restyle is requested for a version whose build has not succeeded
- **THEN** it is refused stating the build has not succeeded
