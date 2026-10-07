## Purpose

Defines how a validated custom-build spec becomes a versioned package on the filesystem: what is refused before Blender sees it, what a build publishes, how versions and their status are recorded and listed, how a spec is edited into a new version, and how each file is served by exact name to the owner.

## Requirements

### Requirement: A spec is validated before Blender sees it
A custom-build document SHALL be validated against the spec schema before any package is created. A document with a field the schema does not define SHALL be refused naming that field (this is the trigger for a generator-extension request, never a reason to fall back to raw Blender code). A value out of the schema's range, a duplicate module id, a module naming an undefined material slot, or a module that does not fit its envelope SHALL be refused naming the field and the problem.

#### Scenario: Unknown field refused by name
- **WHEN** a document carries `modules[0].bevel_mm`
- **THEN** it is refused with a message naming `bevel_mm` and no package is created

#### Scenario: Out-of-range dimension
- **WHEN** a module width is larger than the allowed maximum
- **THEN** it is refused naming `modules[0].width` and the bound

#### Scenario: Shipped template is valid
- **WHEN** the shipped fold-down-desk template is submitted unchanged
- **THEN** it is accepted

### Requirement: A package is a versioned folder on the filesystem
A package SHALL be identified by a short slug the owner chooses (lower-case letters, digits and hyphens, at most 64 characters) that is never used as a path by itself, and each version SHALL be a folder `<render root>/<package-id>/v<N>/` where N starts at 1 and increments per package. Creating a package SHALL write the validated input document and a status file into `v1` and start a build; the service SHALL add no database table for this.

#### Scenario: Create a package
- **WHEN** the owner submits a valid spec with package id `hall-bench`
- **THEN** `hall-bench/v1/` exists with the input document and a status of `queued`, and a build starts

#### Scenario: Invalid package id
- **WHEN** the owner submits a package id containing `/` or `..`
- **THEN** the request is refused naming the id rule and nothing is written

#### Scenario: Existing package id
- **WHEN** the owner creates a package with an id that already has versions
- **THEN** the request is refused, pointing at editing the spec to make a new version

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

### Requirement: Version status is recorded and readable
Each version SHALL carry a status of `queued`, `running`, `succeeded` or `failed`, with timestamps for start and finish and a concise reason on failure, readable through the API. A version that is `queued` or `running` from a previous process SHALL be marked `failed` at startup with the reason that the service restarted.

#### Scenario: Status after a successful build
- **WHEN** a build finishes successfully
- **THEN** the version reads `succeeded` with start and finish times and no reason

#### Scenario: Orphaned job on restart
- **WHEN** the service starts and a version's status is `running`
- **THEN** that version reads `failed` with a reason naming the restart

### Requirement: Editing a spec makes a new version
Submitting an edited spec for an existing package SHALL validate it like a new one and, if valid, create the next version folder with the new input document and start its build. Earlier versions and their files SHALL be left untouched.

#### Scenario: Second version
- **WHEN** the owner submits an edited spec for `hall-bench` whose latest version is `v1`
- **THEN** `hall-bench/v2/` is created and built, and `v1` is unchanged

#### Scenario: Invalid edit
- **WHEN** the edited spec is refused by validation
- **THEN** no new version folder is created and the refusal names the field

### Requirement: Packages and versions are listed
The owner SHALL be able to list every package id with its versions, and read one version's status, which files it has, and which renders exist (`still`, and the turntable frame count).

#### Scenario: List
- **WHEN** two packages exist, one with two versions
- **THEN** the listing names both ids with their version numbers, newest version first

#### Scenario: Read a version
- **WHEN** the owner reads `hall-bench/v2` after a build and a draft turntable
- **THEN** the response reports `succeeded`, the six build files, `still` absent and 12 turntable frames

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

### Requirement: A host without Blender still serves records
When the configured Blender binary is absent or not executable, creating a package, editing a spec and every render SHALL be refused with a 503 stating that Blender is not available on this host, while listing and file serving SHALL keep working.

#### Scenario: Binary missing
- **WHEN** `BLENDER_BIN` points at a file that does not exist and the owner creates a package
- **THEN** the response is 503 with a reason naming Blender, and no version folder is created

### Requirement: The owner approves and unapproves a built version
The owner SHALL be able to approve one version of a piece and to unapprove it through owner-gated routes on that version. Approval SHALL be refused with a 409 and a stated reason when the version's build has not succeeded or when the version is not recorded in the house file (a package created only through the package routes); an unknown package or version SHALL answer 404. Approving a version SHALL clear the approval of any other version of the same piece; approving an approved version or unapproving an unapproved one SHALL succeed and change nothing. Reading a version SHALL report whether it is approved and when. No model tool SHALL approve or unapprove a version.

#### Scenario: Approve a built version
- **WHEN** the owner approves `listening-wall/v4` whose build succeeded
- **THEN** reading `listening-wall/v4` reports it approved with the time, and no other version of `listening-wall` is approved

#### Scenario: Unapprove
- **WHEN** the owner unapproves the approved `listening-wall/v4`
- **THEN** reading it reports it not approved, and no version of `listening-wall` is approved

#### Scenario: Not built yet
- **WHEN** the owner approves `listening-wall/v5` while its build is `running`
- **THEN** the request is refused with a 409 saying the version must be built first, and nothing changes

#### Scenario: Without a login
- **WHEN** the approve route is called without the owner's session
- **THEN** it answers 401 and nothing changes

### Requirement: Only an approved version is priced
Pricing a version SHALL be refused, with a stated reason that the version must be approved first on the Pieces page or the conversation's project panel, when that version is not approved; the refusal SHALL hold for the Researcher's `price_cut_list` and for the owner's pricing route (409 `not_approved`), and SHALL write no pricing record. An existing pricing record SHALL stay readable after its version is unapproved or the approval moves to another version, and reading it SHALL report that its version is no longer approved. Reviews SHALL NOT depend on approval.

#### Scenario: Unapproved version refused
- **WHEN** the Researcher prices `listening-wall/v5` and no version of `listening-wall` is approved
- **THEN** the tool answers that v5 must be approved first on the Pieces page or the project panel, and no pricing record is written

#### Scenario: Owner route refused
- **WHEN** the owner posts a pricing for the unapproved `listening-wall/v5`
- **THEN** the route answers 409 `not_approved` with the same reason, and no pricing record is written

#### Scenario: Approved version priced
- **WHEN** `listening-wall/v4` is approved and the Researcher prices it
- **THEN** a pricing record is written for v4 as before

#### Scenario: Pricing kept after unapproval
- **WHEN** `listening-wall/v4` was priced while approved and is then unapproved
- **THEN** reading that pricing returns it unchanged and reports that its version is no longer approved
