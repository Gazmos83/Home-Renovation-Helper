## ADDED Requirements

### Requirement: A detail render publishes beside the version
A detail still or turntable SHALL render the version's `detail/detail.blend` with the same cameras as the built model's still or turntable. It SHALL publish into the version's `detail/` folder with the same `still.png`, `frames/`, `viewer.html` and `scene.json` layout, verification and atomic publish, and `scene.json` SHALL record source `detail`. Before the render starts, the live Blender's open detail file SHALL be saved when Blender is reachable. When Blender is not reachable, the copy on disk SHALL be rendered as it is. A detail render SHALL NOT replace or alter the version's own `still.png`, `frames/` or `viewer.html`.

#### Scenario: Final detail turntable published
- **WHEN** an approved `final` detail turntable completes
- **THEN** `detail/frames/` holds exactly `frame_000.png` … `frame_035.png` at 1500 × 1500, `detail/viewer.html` names 36 frames, and the version's own `frames/` is unchanged

#### Scenario: Live Blender closed before the render
- **WHEN** a `final` detail still is approved while the live Blender is closed
- **THEN** the render uses `detail/detail.blend` as saved on disk
