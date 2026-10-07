## MODIFIED Requirements

### Requirement: Files are served by exact name only
A version's files SHALL be served only by names from a closed set, each with its media type:
- `model.glb`, `model.blend`, `spec.json`, `cutlist.csv`, `hardware.csv`, `screenshot.png`, `still.png`, `viewer.html`, `scene.json`, `status.json` and `frames/<index>`;
- the same render names under `room/` (`room/still.png`, `room/viewer.html`, `room/scene.json`, `room/frames/<index>`);
- the detail-pass names `detail/still.png`, `detail/viewer.html`, `detail/scene.json`, `detail/frames/<index>` and `detail/screens/<index>`.

`detail/detail.blend` and the detail log SHALL NOT be served. Any other name, any path component, and any file that is not present SHALL answer not found. Every file route SHALL require the owner's session cookie.

#### Scenario: Model served
- **WHEN** the owner requests `model.glb` of a built version
- **THEN** the bytes are served with the glTF binary media type

#### Scenario: Path escape refused
- **WHEN** a request names `../v1/spec.json` or `spec.JSON`
- **THEN** the response is not found and nothing outside the version folder is read

#### Scenario: Not signed in
- **WHEN** a file is requested without a session cookie
- **THEN** the response is 401 with the owner gate's refusal

#### Scenario: Detail screenshot served, detail file not
- **WHEN** the owner requests `detail/screens/0` and then `detail/detail.blend`
- **THEN** the first is served as PNG and the second answers not found
