## MODIFIED Requirements

### Requirement: A build publishes the package files and a screenshot
A successful build SHALL publish the following into the version folder, all at once:
- `model.glb`, `model.blend`, `spec.json`, `cutlist.csv` and `hardware.csv`;
- `screenshot.png`, `front.png`, `side.png` and `top.png`.

Every file SHALL be non-empty and parseable as its format.

The emitted `spec.json` SHALL carry:
- `overall` (width, height, depth in mm);
- `modules` (each module's size and position);
- `layers` (each exported mesh under exactly one of `carcass`, `backs`, `shelves`, `fronts`, `extras`);
- `parts`, `hardware`, `assembly` and `blender_version`.

The build SHALL export one object per cut-list piece, named by its cut-list id and parented to one empty per module.

`model.blend` SHALL also carry the overall dimension lines: one line each for width, height and depth, with its figure in mm taken from `overall`. They are `DIM_` objects under the empty `MOD_Dimensions`, in the collection `09_Dimensions`. The dimension objects SHALL NOT be exported into `model.glb` and SHALL NOT show in `screenshot.png`.

`screenshot.png` SHALL be a Workbench (solid-shading) frame from `CAM_Iso`. `front.png`, `side.png` and `top.png` SHALL be Workbench frames from `CAM_Front`, `CAM_Side` and `CAM_Top`, each showing the dimension lines that view faces:
- front: width and height;
- side: depth and height;
- top: width and depth.

Each of the four SHALL be at most 800 pixels wide and produced without a render tier. A build SHALL NOT produce an Eevee or Cycles image.

#### Scenario: The template builds
- **WHEN** the fold-down-desk template is built with the pinned Blender
- **THEN** the nine files are present and non-empty, `spec.json` lists every exported mesh in exactly one layer, and `cutlist.csv` equals the derived cut list row for row

#### Scenario: Dimension lines in the blend file, not the model
- **WHEN** a piece whose `overall` is 1200 × 2000 × 450 mm is built
- **THEN** `model.blend` holds the width, height and depth lines with the figures `1200 mm`, `2000 mm` and `450 mm`, and `model.glb` holds no `DIM_` node

#### Scenario: Straight-on views
- **WHEN** a build succeeds
- **THEN** `front.png`, `side.png` and `top.png` are Workbench PNGs at most 800 pixels wide, and the front view shows the width and height figures

#### Scenario: A failed build publishes nothing
- **WHEN** the build fails after writing some files to its staging area
- **THEN** the version folder holds no build files, the status is `failed` with a concise reason, and no staging directory remains

#### Scenario: Reason is safe to show
- **WHEN** a build fails with a diagnostic containing the host path of the render root
- **THEN** the recorded reason omits that path and is at most 500 characters

### Requirement: Files are served by exact name only
A version's files SHALL be served only by names from a closed set, each with its media type:
- `model.glb`, `model.blend`, `spec.json`, `cutlist.csv`, `hardware.csv`, `screenshot.png`, `front.png`, `side.png`, `top.png`, `still.png`, `viewer.html`, `scene.json`, `status.json` and `frames/<index>`;
- the same render names under `room/` (`room/still.png`, `room/viewer.html`, `room/scene.json`, `room/frames/<index>`);
- the detail-pass names `detail/still.png`, `detail/viewer.html`, `detail/scene.json`, `detail/frames/<index>` and `detail/screens/<index>`.

`detail/detail.blend` and the detail log SHALL NOT be served. Any other name, any path component, and any file that is not present SHALL answer not found. Every file route SHALL require the owner's session cookie.

#### Scenario: Model served
- **WHEN** the owner requests `model.glb` of a built version
- **THEN** the bytes are served with the glTF binary media type

#### Scenario: Straight-on view served
- **WHEN** the owner requests `front.png` of a version built with the views, and then `front.png` of a version built before them
- **THEN** the first is served as PNG and the second answers not found

#### Scenario: Path escape refused
- **WHEN** a request names `../v1/spec.json` or `spec.JSON`
- **THEN** the response is not found and nothing outside the version folder is read

#### Scenario: Not signed in
- **WHEN** a file is requested without a session cookie
- **THEN** the response is 401 with the owner gate's refusal

#### Scenario: Detail screenshot served, detail file not
- **WHEN** the owner requests `detail/screens/0` and then `detail/detail.blend`
- **THEN** the first is served as PNG and the second answers not found
