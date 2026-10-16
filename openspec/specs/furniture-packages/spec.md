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
The owner SHALL be able to approve one version of a piece and to unapprove it through owner-gated routes on that version. Approval SHALL be refused with a 409 and a stated reason when the version's build has not succeeded or when the version is not recorded in the house file (a package created only through the package routes); an unknown package or version SHALL answer 404. Unapproving SHALL be refused with a 409 and a stated reason naming the composition and its version when that piece version is placed in an approved composition version. Approving a version SHALL clear the approval of any other version of the same piece; approving an approved version or unapproving an unapproved one SHALL succeed and change nothing. Reading a version SHALL report whether it is approved and when. No model tool SHALL approve or unapprove a version.

#### Scenario: Approve a built version
- **WHEN** the owner approves `listening-wall/v4` whose build succeeded
- **THEN** reading `listening-wall/v4` reports it approved with the time, and no other version of `listening-wall` is approved

#### Scenario: Unapprove
- **WHEN** the owner unapproves the approved `listening-wall/v4` and no approved composition places it
- **THEN** reading it reports it not approved, and no version of `listening-wall` is approved

#### Scenario: Unapprove refused while placed in an approved room
- **WHEN** approved `Wohnen` version 2 places `listening-wall` v4 and the owner unapproves v4
- **THEN** the request is refused with a 409 naming `Wohnen` version 2, and v4 stays approved

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

### Requirement: A module can carry adjustable shelves and name its hardware items
A module SHALL accept:
- a number of adjustable shelves, from 0 to 20, with 0 as the default;
- a shelf-pin item key, used when the module has adjustable shelves.

A door entry SHALL accept a hinge item key. Without one, the door SHALL use `hinge-concealed-110`, as today. An item key SHALL be a hardware key, the same key a price-list entry and a data sheet use.

The cut list SHALL hold one adjustable-shelf row per module that has adjustable shelves (one per bay when the module's bays differ in width, as set out in "A module can carry vertical dividers"). The row SHALL be cut between the sides (or the bay's sides) at the back-reduced depth, less the adjustable-shelf clearance. The hardware SHALL hold one line per shelf-pin item. Its quantity SHALL be the sum over that item's adjustable shelf boards of each board's pins per shelf, taken from, in this order:
1. the pins per shelf on the item's data sheet;
2. otherwise, the shelf-pin count rule in the inputs, applied to the board's cut width;
3. with neither, the line SHALL have no quantity, as set out in the hardware-drilling spec.

The line's note SHALL name where the count came from: the data sheet, or the rule's id and its source. Hinge lines SHALL be keyed by the door's hinge item. Their count per door SHALL be decided as set out in the hardware-drilling spec: the item's data-sheet count table, else the hinge-count rule in the inputs, else the built-in fallback. Their note SHALL name which of the three decided. When a hinge's data sheet names a mounting-plate item, the hardware SHALL hold that plate's line with one plate per hinge.

A built version SHALL draw each adjustable shelf as a board inside its module. When the module states no shelf spacing or positions, the fixed and adjustable shelves SHALL be spaced evenly together. With a spacing or positions, they SHALL be placed as set out in "A module can state its shelf spacing or shelf positions". A module with no adjustable shelves SHALL be drawn exactly as before. No hole, pin, hinge cup or plate SHALL be drawn.

A document with no new field SHALL derive the same cut list and hardware as before. A derivation without inputs (no data sheets and no rules) SHALL give the same hardware as before this change.

#### Scenario: Adjustable shelves listed
- **WHEN** a 600 mm wide module with 18 mm sides has two adjustable shelves and shelf pin `shelf-pin`, whose data sheet gives 4 pins per shelf
- **THEN** the cut list holds one adjustable-shelf row with quantity 2, and the hardware holds `shelf-pin` with quantity 8

#### Scenario: Pin count from the rule
- **WHEN** the 800 mm wide Kommode module with 18 mm sides has two adjustable shelves (762 mm boards), `shelf-pin` has no data sheet, and the inputs hold the `shelf-pin-count` rule
- **THEN** the hardware holds `shelf-pin` with quantity 8 and a note naming `shelf-pin-count` and its owner note

#### Scenario: Wide shelf takes the beyond count
- **WHEN** a module's adjustable shelf is cut 1162 mm wide, `shelf-pin` has no data sheet, and the inputs hold the `shelf-pin-count` rule
- **THEN** that board counts 5 pins

#### Scenario: Data sheet wins over the pin rule
- **WHEN** `shelf-pin`'s data sheet gives 6 pins per shelf, and the inputs also hold the `shelf-pin-count` rule
- **THEN** each adjustable shelf counts 6 pins, and the note names the data sheet

#### Scenario: No sheet and no rule
- **WHEN** a module has adjustable shelves, and its inputs hold neither a shelf-pin data sheet nor a pin-count rule
- **THEN** the shelf-pin line has no quantity, as before this change

#### Scenario: Hinge count from the rule
- **WHEN** a module has two 1550 mm hinged doors without a hinge data sheet, and the inputs hold the `hinge-count` rule
- **THEN** the hinge line counts 8 hinges and its note names `hinge-count` and its owner note

#### Scenario: Default hinge unchanged
- **WHEN** the shipped fold-down-desk template is derived
- **THEN** its cut list and hardware equal those derived before this change, row for row

#### Scenario: Hinge item named
- **WHEN** a door entry names hinge `hinge-blum-clip-110`
- **THEN** its hinges are listed under `hinge-blum-clip-110`, and no `hinge-concealed-110` line is added for that door

#### Scenario: Unknown module field
- **WHEN** a module carries `pin_pitch_mm`
- **THEN** it is refused naming `pin_pitch_mm`, and the refusal becomes a generator-extension request

### Requirement: A custom build can carry wall-hung shelves on brackets
A custom-build document SHALL accept an optional list of wall shelves. Each wall shelf SHALL have:
- an id, unique among the document's wall shelves, modules and extra parts, and a name;
- the position of the board's left end and underside, in mm in the build's frame;
- the board's length, depth and material slot;
- the bracket item key;
- optionally, the owner's bracket positions, in mm from the board's left end to each bracket's centre.

Without the owner's positions, the bracket count and positions SHALL be calculated from the bracket rules:
- the count is the minimum the count rule gives for the board's length;
- the two outer brackets are listed at the spacing rule's end-distance range from each end, as cited, for example "100–200 mm from each end", and never at a value picked inside it;
- any other brackets are listed as "evenly spaced between them", in words, with no number.

With the owner's positions, those positions SHALL be used as an override. They SHALL be judged by the bracket checks, which can only warn.

When a bracket rule is missing, or the board is not longer than twice the shortest end distance, the positions SHALL be blank and the bracket line SHALL have no quantity, with a warning as set out in the hardware-drilling spec.

The document SHALL be refused, naming the field and the problem, when:
- a wall shelf names an undefined material slot;
- an owner's bracket position is not inside the board, or the positions are not strictly increasing;
- the owner's list is given but empty, or holds more than 20 positions;
- a shelf lies outside the envelope.

A field a wall shelf does not define SHALL be refused by name, as for any other part of the document.

The cut list SHALL hold one row per board, with the board's length, depth and material. The hardware SHALL hold one line per bracket item, with a quantity equal to the brackets on every shelf that uses it. The drilling list SHALL give each board's bracket positions and say whether they were calculated or set by the owner.

A built version SHALL draw each board as one object named by the shelf's id, under one empty per shelf. Brackets SHALL NOT be drawn.

`revise_package` SHALL be able to add a wall shelf, remove one, and change a shelf's fields, including setting or clearing its bracket positions. A change naming a shelf the document does not contain SHALL be refused, naming the shelves it does contain.

#### Scenario: Brackets calculated
- **WHEN** a document carries a 1200 mm oak wall shelf, 250 mm deep, with no bracket positions, and the shipped bracket rules apply
- **THEN** it is accepted, the cut list holds one 1200 × 250 mm oak board row, the bracket line has quantity 2, and the drilling list gives two calculated brackets "100–200 mm from each end", with the source, and no single end distance

#### Scenario: Owner's positions kept
- **WHEN** a 1200 mm wall shelf lists brackets at 150, 600 and 1050 mm
- **THEN** the bracket line has quantity 3, the drilling list gives those positions marked as set by the owner, and no bracket warning is shown

#### Scenario: Bracket outside the board
- **WHEN** a 900 mm wall shelf lists a bracket at 950 mm
- **THEN** it is refused, naming `wall_shelves[0].bracket_positions_mm` and the board's length, and no package is created

#### Scenario: Positions out of order
- **WHEN** a wall shelf lists brackets at 600, 150 and 1050 mm
- **THEN** it is refused, naming `wall_shelves[0].bracket_positions_mm` as not strictly increasing

#### Scenario: Unknown wall-shelf field
- **WHEN** a wall shelf carries `load_kg`
- **THEN** it is refused, naming `load_kg`, and the refusal becomes a generator-extension request

#### Scenario: Board drawn, brackets not
- **WHEN** a version with a wall shelf is built headless
- **THEN** the model holds the board object and the shelf's empty, and no bracket object

#### Scenario: Bracket positions set in a revision
- **WHEN** the Designer revises a package, setting a shelf's brackets to 150, 600 and 1050 mm
- **THEN** a new version is proposed with those positions as the owner's override, and its change lines name the shelf and its old and new positions

### Requirement: A build receives its version's hardware inputs and publishes the drilling list
The headless build SHALL receive the version's saved hardware inputs together with its spec. Its emitted `spec.json` SHALL carry `drilling`:
- the drilling list per part;
- the drilling-work counts;
- the warnings;
- whether the list is complete.

Its `cutlist.csv` and `hardware.csv` SHALL equal the derivation from the same spec and inputs, row for row. A build of a version with no saved inputs SHALL run as before.

#### Scenario: Build parity with inputs
- **WHEN** a version with adjustable shelves and saved inputs is built with the pinned Blender
- **THEN** `cutlist.csv` and `hardware.csv` equal the backend's derivation from the same spec and inputs, and `spec.json` `drilling` equals the backend's drilling list

### Requirement: A module can state its shelf spacing or shelf positions
A module SHALL accept two optional fields. A module MAY state one of them, never both.
- **Shelf spacing.** `shelf_spacing_mm` is a whole number of millimetres: the clear gap between boards. The first shelf's underside SHALL sit one gap above the top face of the bottom panel. Each next shelf's underside SHALL sit one gap plus one board thickness above the previous one.
- **Shelf positions.** `shelf_positions_mm` is a list of whole millimetres: the height of each shelf's underside above the top face of the bottom panel, lowest first. It SHALL hold one entry per shelf, counting fixed and adjustable shelves together.

Shelves SHALL be placed from the bottom up, fixed shelves first, then adjustable shelves, as with even spacing. The board thickness is the carcass slot's thickness. Without either field, shelves SHALL be spaced evenly as before.

The document SHALL be refused, naming the field and the problem, when:
- both fields are given;
- either field is given and the module has no shelves;
- the positions list does not have one entry per shelf;
- the positions are not increasing by at least one board thickness;
- a shelf's top face would be above the underside of the top panel, with the inner height named.

A built version SHALL draw each shelf at its calculated height. The cut list and hardware SHALL be the same as with even spacing; only the heights change. `revise_package` SHALL be able to set and clear either field. Setting one SHALL remove the other, and the change lines SHALL name both.

#### Scenario: Four shelves 355 mm apart
- **WHEN** a module 1600 mm high with 18 mm carcass has 4 fixed shelves and `shelf_spacing_mm` 355
- **THEN** it is accepted, and the shelves' undersides are 355, 728, 1101 and 1474 mm above the top face of the bottom panel

#### Scenario: Spacing too large
- **WHEN** a module 1200 mm high with 18 mm carcass has 4 shelves and `shelf_spacing_mm` 355
- **THEN** it is refused, naming `modules[0].shelf_spacing_mm` and the inner height of 1164 mm, and no package is created

#### Scenario: Uneven positions
- **WHEN** a module with 3 shelves lists `shelf_positions_mm` 300, 700 and 1300
- **THEN** it is accepted, and the shelves are drawn at those heights

#### Scenario: Wrong number of positions
- **WHEN** a module with 3 shelves lists two positions
- **THEN** it is refused, naming `modules[0].shelf_positions_mm` and the 3 shelves expected

#### Scenario: Spacing and positions together
- **WHEN** a module gives both `shelf_spacing_mm` and `shelf_positions_mm`
- **THEN** it is refused, naming both fields

#### Scenario: Spacing set in a revision
- **WHEN** module `cabinet` has 4 shelves at stated positions, and the Designer revises it with `shelf_spacing_mm` 355
- **THEN** the proposed version has the spacing and no positions, and the change lines name both

#### Scenario: Old document unchanged
- **WHEN** a document with neither field is derived and built
- **THEN** its cut list, hardware and shelf heights equal those of the same document before this change

### Requirement: A module can carry vertical dividers
A module SHALL accept `dividers`, a count from 0 to 10, with 0 as the default. It SHALL also accept an optional `divider_positions_mm`: the distance from the inner face of the left side to each divider's left face, in whole millimetres, lowest first, one entry per divider. On a module with a side fold, that distance SHALL be measured from the unbent left side's inner face (the carcass thickness from the module's left face).

A module SHALL also accept an optional `divider_spans`: one entry per divider, left to right, each with:
- `from_board`: `"bottom"` or a shelf number from 1, counting every shelf (fixed and adjustable) from the lowest, the board the divider stands on;
- `to_board`: `"top"` or a shelf number, the board the divider reaches.

A shelf named by a span SHALL be a fixed shelf: an adjustable shelf cannot anchor a divider.

Without `divider_spans`, every divider SHALL run between the bottom panel and the top panel. A divider's length SHALL be the clear gap between the top face of its `from_board` and the underside of its `to_board`, rounded down to a whole millimetre.

A divider SHALL:
- run between its two boards;
- be cut in the carcass slot's material and thickness, at the back-reduced depth;
- be drawn as its own object in the `carcass` layer.

Without positions, the dividers SHALL split the inner width into equal bays; the bay width is rounded down to a whole millimetre. On a module with a side fold, they SHALL instead split into equal bays the narrowest inner opening found along their spans and the full back-reduced depth.

A shelf board (fixed or adjustable) SHALL be split into bays only by the dividers whose span crosses that shelf's height; a divider's own `from_board` and `to_board` are not split by it. Fixed shelves SHALL be cut to the bay's width. Adjustable shelves SHALL be cut to the bay's width less the adjustable-shelf clearance. On a folded module, a board or bay segment next to a folded side SHALL be cut to the smallest width along that board's thickness and depth, rounded down to a whole millimetre.

Cut-list rows:
- with full-height dividers on a module without a fold, as before: when every bay has the same width, each shelf kind keeps its one row (`<module>-shelf`, `<module>-adjustable-shelf`) with its quantity multiplied by the bays; when the bays differ, each bay has its own rows, named with `-bay-<n>` counted from the left;
- otherwise the shelf boards of one kind SHALL be grouped by cut width: one width keeps `<module>-shelf` or `<module>-adjustable-shelf` with its quantity; several widths become `<module>-shelf-<n>` or `<module>-adjustable-shelf-<n>`, numbered by first appearance from the lowest level and, within a level, from the left, each with notes naming the shelf levels and bays it covers;
- the dividers SHALL be one `<module>-divider` row while they share a length, else one `<module>-divider-<n>` row per length, numbered from the left.

The confirmat screws SHALL be 8 per carcass, plus 4 per fold joint, plus 4 per fixed shelf board, plus 4 per divider. Shelf pins SHALL be the pins per shelf times the adjustable shelf boards.

The document SHALL be refused, naming the field and the problem, when:
- positions are given and their number differs from `dividers`;
- positions are given without dividers;
- positions are not increasing by more than one board thickness;
- a divider lies outside the inner width;
- any bay would be 0 mm wide or less;
- `divider_spans` is given and its number differs from `dividers`, or it is given without dividers;
- a span names a shelf number the module does not have;
- a span names an adjustable shelf, naming that shelf number and that only fixed shelves can anchor a divider;
- a span's `from_board` is not below its `to_board`;
- on a folded module, a divider would cut into a folded side, or leave a bay 0 mm wide or less, anywhere along its span.

A module without dividers, and a module without a fold whose dividers have no `divider_spans`, SHALL derive and be drawn exactly as before. `revise_package` SHALL be able to set the count, set or clear the positions, and set or clear the spans; `[]` SHALL clear `divider_spans` back to full height, and setting `dividers` to 0 SHALL clear the spans as well.

#### Scenario: Two dividers, equal bays
- **WHEN** a module 1000 mm wide with 18 mm carcass has 2 dividers and 3 fixed shelves
- **THEN** the cut list holds one divider row with quantity 2, and one fixed-shelf row 309 mm long with quantity 9; the confirmat line is 8 + 4 × 9 + 4 × 2 = 52

#### Scenario: Positioned divider, unequal bays
- **WHEN** a module 1000 mm wide with 18 mm carcass has 1 divider at 400 mm and 2 fixed shelves
- **THEN** the cut list holds `<module>-shelf-bay-1` 400 mm long with quantity 2 and `<module>-shelf-bay-2` 546 mm long with quantity 2

#### Scenario: Shelves split by dividers in the model
- **WHEN** a version with 2 dividers and 3 shelves 355 mm apart is built headless
- **THEN** the model holds two divider objects and nine shelf objects, and every shelf's underside is at its calculated height

#### Scenario: Divider from the top shelf to the top
- **WHEN** module `cabinet` is 800 × 2000 × 400 mm with 18 mm carcass, 12 mm back, 4 fixed shelves, 1 divider and `divider_spans` [{`from_board`: 4, `to_board`: "top"}]
- **THEN** it is accepted, the cut list holds `cabinet-divider` 383 × 388 mm with quantity 1 and `cabinet-shelf` 764 mm long with quantity 4, and the confirmat line is 8 + 4 × 4 + 4 = 28

#### Scenario: Divider crosses only the shelf below it
- **WHEN** a module 1000 × 1200 mm with 18 mm carcass has 3 fixed shelves, 1 divider at 400 mm and `divider_spans` [{`from_board`: "bottom", `to_board`: 2}]
- **THEN** the cut list holds `<module>-divider` 573 mm long, `<module>-shelf-1` 400 mm with quantity 1, `<module>-shelf-2` 546 mm with quantity 1 and `<module>-shelf-3` 964 mm with quantity 2, and the confirmat line is 8 + 4 × 4 + 4 = 28

#### Scenario: Partial divider drawn in the model
- **WHEN** the `cabinet` with the divider from shelf 4 to the top is built headless
- **THEN** the model holds one divider object whose bottom face meets the top face of the fourth shelf and whose top face meets the underside of the top panel, and four whole shelf objects

#### Scenario: Divider on a folded module
- **WHEN** that `cabinet` also has the 26° left inside height fold from 1100 mm and no divider positions
- **THEN** it is accepted, the divider splits the narrowest opening along its span (448 to 782 mm from the module's left face) into two 158 mm bays, its left face is 588 mm from the unbent left side's inner face, the cut list holds `cabinet-divider` 383 × 388 mm, and the confirmat line is 8 + 4 + 4 × 4 + 4 = 32

#### Scenario: Divider cuts into a folded side
- **WHEN** the folded `cabinet` lists `divider_positions_mm` [100] with the divider from shelf 4 to the top
- **THEN** it is refused, naming `modules[0].divider_positions_mm` and the folded side, and no package is created

#### Scenario: Span on a missing shelf
- **WHEN** a module with 2 fixed shelves has `divider_spans` [{`from_board`: 3, `to_board`: "top"}]
- **THEN** it is refused, naming `modules[0].divider_spans`

#### Scenario: Span on an adjustable shelf
- **WHEN** module `cabinet` has 4 adjustable shelves and no fixed shelf, and `divider_spans` [{`from_board`: 4, `to_board`: "top"}]
- **THEN** it is refused, naming `modules[0].divider_spans`, shelf 4, and that only fixed shelves can anchor a divider

#### Scenario: Spans cleared in a revision
- **WHEN** module `cabinet` has the divider from shelf 4 to the top, and the Designer revises it with `divider_spans` []
- **THEN** the proposed version's divider runs from the bottom panel to the top panel, and the change lines name the cleared span

#### Scenario: Divider outside the module
- **WHEN** a module with 964 mm inner width lists a divider at 960 mm
- **THEN** it is refused, naming `modules[0].divider_positions_mm` and the inner width

#### Scenario: Unknown divider field
- **WHEN** a module carries `divider_material`
- **THEN** it is refused, naming `divider_material`, and the refusal becomes a generator-extension request

### Requirement: A package version can be deleted
The owner SHALL be able to delete one version of a package. Deleting SHALL remove the version's folder with everything in it: the input, the model, the screenshot and views, the renders, the cut list and the drilling list. The service SHALL refuse the delete, without changing anything, and say why in plain words when:
- the version is approved ("unapprove version N first");
- a room composition version places it (naming the composition and its version);
- its build or one of its renders is queued or running;
- the version does not exist.

Deleting the only remaining version of a package SHALL delete the package. Version numbers SHALL never be reused. After a deletion, the next version of the package SHALL be numbered one above the highest version it ever had, whether or not that version still exists. Deleting is an owner route only; no agent tool SHALL delete a version.

#### Scenario: Delete an older version
- **WHEN** `hall-bench` has versions 1 to 4, version 4 is approved, and the owner deletes version 2
- **THEN** `hall-bench/v2/` no longer exists, versions 1, 3 and 4 are unchanged, and version 4 stays approved

#### Scenario: Approved version refused
- **WHEN** the owner deletes `hall-bench` version 4 while it is approved
- **THEN** the delete is refused saying to unapprove version 4 first, and nothing is removed

#### Scenario: Version placed in a composition
- **WHEN** composition `Living room` version 3 places `hall-bench` version 2 and the owner deletes `hall-bench` version 2
- **THEN** the delete is refused naming `Living room` version 3, and nothing is removed

#### Scenario: Version still building
- **WHEN** the owner deletes a version whose build is running
- **THEN** the delete is refused saying the version is still building

#### Scenario: Numbers are not reused
- **WHEN** `hall-bench` has versions 1 to 5, the owner deletes version 5 and then a revision is confirmed
- **THEN** the new version is version 6

#### Scenario: Last version deletes the package
- **WHEN** `hall-bench` has only version 1 and the owner deletes it
- **THEN** the `hall-bench` folder no longer exists and the package is no longer listed

### Requirement: A package holds at most 15 versions
A package SHALL hold at most 15 versions at a time. Making a new version of a package that already holds 15 SHALL be refused before anything is written. The refusal SHALL say that the piece has 15 versions and that one must be deleted first on the Pieces page or the Project panel. This SHALL apply to every way a version is made: the package route, a revision, and a rebuild. A version that was deleted SHALL NOT count toward the limit. The limit SHALL be set in one place in code.

#### Scenario: Sixteenth version refused
- **WHEN** `hall-bench` holds 15 versions and the owner submits an edited spec to the package route
- **THEN** the request is refused saying the piece has 15 versions and one must be deleted first, and no folder is written

#### Scenario: Room again after a delete
- **WHEN** `hall-bench` holds 15 versions numbered 1 to 15, the owner deletes version 3, and a revision is confirmed
- **THEN** version 16 is made and the package holds 15 versions

### Requirement: A module can fold a carcass side at an angle
A module SHALL accept an optional `side_folds` list of at most two entries. Each entry SHALL have:
- `side`: `left` or `right`;
- `from_mm`: a whole millimetre, the kink;
- `along`: `height` or `depth`;
- `angle_deg`: a whole degree from 1 to 89;
- `towards`: `inside` or `outside`.

At most one fold per side. `from_mm` is measured from the module's bottom face when `along` is `height`, and from the module's front face when `along` is `depth`.

The named side SHALL run straight to `from_mm` and then leave its original plane by `angle_deg` from that axis. `inside` moves the side toward the opposite side after the kink; `outside` moves it away. The inset at a run of `h` millimetres past the kink SHALL be `h × tan(angle_deg)`, rounded to the nearest whole millimetre, with halves rounded away from zero.

The module's stated `width`, `height` and `depth` SHALL remain the unbent box (the part before the kink). The build's `overall`, envelope fit, module overlap and room-fit size SHALL use the axis-aligned bounding box of the folded solid, which grows past the stated box when a fold is `outside`.

The folded side SHALL be two rectangular boards joined at the kink, in the carcass material and thickness, at the back-reduced depth. The unfolder side SHALL stay one full-height (or full-depth) rectangle. Each horizontal board (bottom, top, each fixed shelf, each adjustable shelf) SHALL be a rectangle cut to the smallest inner width along that board's thickness, rounded down to a whole millimetre; an adjustable shelf SHALL then be shortened by the adjustable-shelf clearance. The back SHALL be one board whose net outline follows the side profile; its cut-list row SHALL be the grain-aligned bounding rectangle, with notes that name the net shape.

A folded module MAY carry overlay fronts. Each door, flap or drawer front SHALL follow the folded carcass outline in the front plane, with a 3 mm gap (1.5 mm at every edge). Several doors of one entry SHALL split on verticals at equal shares of the unbent width. A front whose outline is a rectangle SHALL stay a rectangular cut-list row, as today. A front whose outline is not a rectangle SHALL be one board whose net follows that outline; its cut-list row SHALL be the grain-aligned bounding rectangle, with notes that name the net shape. A drawer box SHALL stay a rectangle cut to the smallest inner width along that drawer's height, less the runner side clearance.

A folded module MAY carry dividers, full-height or spanning between named boards, as set out in "A module can carry vertical dividers".

A built version SHALL draw those fronts as their own objects in the `fronts` layer, in the front plane, closed; an n-gon front is one mesh named by its cut-list id.

Cut-list row ids:
- with no fold, `{module}-side` quantity 2, as today;
- with a fold, `{module}-side-{left|right}` for an unfolder side, and `{module}-side-{left|right}-lower` plus `{module}-side-{left|right}-upper` (height) or `-front` plus `-back` (depth) for a folded side;
- `{module}-top` and `{module}-bottom` as separate rows when their cut sizes differ, otherwise `{module}-top-bottom` quantity 2 as today;
- without dividers, each fixed or adjustable shelf whose width differs from the others of its kind as its own `{module}-shelf-{n}` or `{module}-adjustable-shelf-{n}` row, lowest first; equal widths keep `{module}-shelf` or `{module}-adjustable-shelf` with quantity, as today; with dividers, shelf rows are grouped by cut width as set out in "A module can carry vertical dividers".

Each joining edge's notes SHALL name the mitre and the angle in degrees. The confirmat count SHALL be 8 per carcass, plus 4 per fold joint, plus 4 per fixed shelf board, plus 4 per divider. The derived assembly SHALL include a step that names the side, the angle and `from_mm`.

A built version SHALL draw the carcass boards as their own objects in the `carcass` and `backs` layers, the upper or back side board rotated by `angle_deg` so it meets the lower or front board at the kink. Dimension lines SHALL follow the folded bounding box.

The document SHALL be refused, naming the field and the problem, when:
- two entries name the same side;
- `along` is `height` and `from_mm` is not strictly between the carcass thickness and height minus that thickness;
- `along` is `depth` and `from_mm` is not strictly between 1 mm and the back-reduced depth;
- the inset at the far end rounds to 0 mm;
- the inner opening at any point along the fold is less than 1 mm;
- a front's remaining width at any height along that front is below the minimum front size;
- the folded bounding box lies outside the envelope, or overlaps another module's folded bounding box.

`revise_package` SHALL be able to set `side_folds` to a new list. `[]` SHALL clear every fold. A module with no `side_folds` SHALL derive and be drawn exactly as before.

#### Scenario: Left side 26 degrees from 1100 mm
- **WHEN** module `cabinet` is 800 × 2000 × 400 mm with 18 mm carcass, 12 mm back, no shelves, and one fold `{side: left, from_mm: 1100, along: height, angle_deg: 26, towards: inside}`
- **THEN** it is accepted, the left-side inset at the top is 439 mm, the cut list holds `cabinet-side-left-lower` 1100 × 388 mm, `cabinet-side-left-upper` 1001 × 388 mm with notes naming a 26° mitre, `cabinet-side-right` 2000 × 388 mm, separate top and bottom rows, and the confirmat line is 12

#### Scenario: Outside fold grows overall
- **WHEN** the same module's fold is `towards: outside` and the document has no envelope
- **THEN** `overall` width is 800 + 439 = 1239 mm

#### Scenario: Fold pinches the opening
- **WHEN** a 400 mm wide module with 18 mm carcass has a left inside height fold from 100 mm at 45°
- **THEN** it is refused, naming `modules[0].side_folds` and the remaining inner width, and no package is created

#### Scenario: Two doors follow a left height fold
- **WHEN** the 800 × 2000 × 400 mm cabinet has the 26° left inside height fold from 1100 mm and two hinged doors
- **THEN** it is accepted, the right door is a rectangle, the left door's net follows the left profile with a 3 mm gap, its cut-list row is the bounding rectangle with notes naming the net, and a built version draws both in the `fronts` layer

#### Scenario: Adjustable shelf on a fold uses the pinched width
- **WHEN** that cabinet has one adjustable shelf whose board sits above 1100 mm
- **THEN** the adjustable-shelf row is cut to the smallest inner width along that board, less the adjustable-shelf clearance

#### Scenario: Front too narrow at the top is refused
- **WHEN** a folded module has a door whose remaining width at some height along that door is below the minimum front size
- **THEN** it is refused, naming `modules[0].fronts`, and no package is created

#### Scenario: Dividers accepted on a folded module
- **WHEN** a module with a side fold also lists `dividers` 1 and the divider fits inside the folded opening along its whole span
- **THEN** it is accepted, and the cut list holds a divider row

#### Scenario: Two folds on the same side
- **WHEN** `side_folds` lists two entries with `side: left`
- **THEN** it is refused, naming `modules[0].side_folds`

#### Scenario: Fold drawn in the model
- **WHEN** a version with the 26° left height fold is built headless
- **THEN** the model holds the lower and upper left-side objects meeting at 1100 mm, the upper board at 26° to vertical, and the back's net outline follows the left profile

#### Scenario: Folds cleared in a revision
- **WHEN** module `cabinet` has a left fold and the Designer revises it with `side_folds` []
- **THEN** the proposed version has no folds, the change lines name the cleared fold, and the sides go back to one `{id}-side` row of quantity 2

#### Scenario: Old document unchanged
- **WHEN** a document with no `side_folds` is derived and built
- **THEN** its cut list, hardware, assembly, `overall` and model equal those of the same document before this change

### Requirement: A module can state each shelf's kind
A module SHALL accept an optional `shelf_kinds`: one entry per shelf, lowest first, each `"fixed"` or `"adjustable"`. The number of entries SHALL equal `shelves` plus `adjustable_shelves`, and the number of each kind SHALL equal its count. Without `shelf_kinds`, the fixed shelves SHALL take the lowest heights and the adjustable shelves the rest, as before. Shelf heights (even spacing, `shelf_spacing_mm` or `shelf_positions_mm`) SHALL NOT depend on the kinds.

Each shelf SHALL be derived and drawn by its own kind: a fixed shelf as a fixed-shelf board with 4 confirmat screws, an adjustable shelf as an adjustable-shelf board less the clearance, with its pins. `revise_package` SHALL be able to set `shelf_kinds`; `[]` SHALL clear it back to fixed shelves lowest. The document SHALL be refused, naming `shelf_kinds`, when its length or its kind counts disagree with `shelves` and `adjustable_shelves`. A module without `shelf_kinds` SHALL derive and be drawn exactly as before.

#### Scenario: Top shelf fixed, the rest adjustable
- **WHEN** module `cabinet` had 4 adjustable shelves and is revised to `shelves` 1, `adjustable_shelves` 3 and `shelf_kinds` ["adjustable", "adjustable", "adjustable", "fixed"]
- **THEN** the cut list holds one fixed-shelf board and three adjustable-shelf boards at the same heights as before, the confirmat line rises by 4, the shelf-pin line counts 3 shelves instead of 4, and the top board in the model is the fixed one

#### Scenario: Kinds disagree with the counts
- **WHEN** a module with `shelves` 1 and `adjustable_shelves` 3 lists `shelf_kinds` ["fixed", "fixed", "adjustable", "adjustable"]
- **THEN** it is refused, naming `modules[0].shelf_kinds`

#### Scenario: No kinds, unchanged
- **WHEN** a document has no `shelf_kinds`
- **THEN** its cut list, hardware and model equal those of the same document before this change

### Requirement: A revision preview lists hardware and cut-list changes
The confirmation `revise_package` shows SHALL list, after the change lines, every hardware line whose quantity changes (item, old quantity → new quantity, or added / removed) and every cut-list row that is added, removed or changes quantity or size, derived from the latest version and the revised document. A revision that changes no hardware or cut-list row SHALL show no such lines.

#### Scenario: Fixing a shelf in the preview
- **WHEN** the owner agrees to fix the top of four adjustable shelves and the Designer proposes the revision
- **THEN** the preview lists the confirmat line rising by 4, the shelf-pin line falling by one shelf's pins, a fixed-shelf row added and the adjustable-shelf quantity falling from 4 to 3

#### Scenario: Divider in the preview
- **WHEN** the Designer proposes the divider from shelf 4 to the top on `cabinet`
- **THEN** the preview lists `cabinet-divider` 383 × 388 mm added and the confirmat line 24 → 28

### Requirement: An extra part can state where each of its pieces sits
A custom-build extra part SHALL accept optional `placements`: a list with exactly one entry per piece, so its length equals the part's `qty`. A piece is described in its own terms: its length, its width, and its thickness from the part's material slot. Its reference corner is the corner at the start of its length, on the edge and face it is measured from. Each entry SHALL give:
- `x`, `y`, `z`: where the reference corner sits, in mm in the build's frame, as for modules and wall shelves (x to the right, y towards the back, z up);
- `length_along` and `width_along`: the axis (`x`, `y` or `z`) the piece's length and width run along before any turn, never the same; the thickness runs along the remaining axis;
- optionally `roll_deg` (−89 to 89, not 0): the piece turns about its own length line through the reference corner, a positive angle turning its width towards its thickness side;
- optionally `tilt`: `towards` (an axis other than `length_along`) and `angle_deg` (−89 to 89, not 0). After any roll, the piece's length turns about the reference corner towards that axis by that angle, a positive angle towards the axis's positive direction. "Length along x, tilt 35° towards z" is a brace rising to the right.

A document whose placements disagree with `qty`, whose `length_along` equals `width_along`, or whose `tilt.towards` equals `length_along`, SHALL be refused naming the field. When the document has an envelope, a placed piece SHALL be refused, naming the part, unless every corner of the piece after its turns lies inside the envelope. When it has no envelope, the overall size SHALL include every corner of every placed piece after its turns. Unplaced pieces SHALL NOT count.

A build SHALL draw each placed piece at its stated position, orientation and turns, as exact geometry. Each piece is one object named by its cut-list id, as for every other part, under the extras empty and in the `extras` layer. An extra part without `placements` SHALL still be laid flat beside the build. Placements SHALL NOT change any cut-list row's quantity, length, width, thickness or material, nor the hardware, the drilling list or the pricing.

A part override that changes an extra part's quantity SHALL keep the existing rule: the drawing follows the overridden count, extra copies are added beside the last piece and surplus pieces are dropped.

#### Scenario: Placed frame drawn assembled
- **WHEN** a document has extra part `top-frame` (qty 1, 1200 × 60 mm, 18 mm slot) placed at x 0, y 0, z 900, length along x, width along y
- **THEN** `model.blend`, `model.glb` and `screenshot.png` show `top-frame` as a 1200 × 60 × 18 mm board with its corner at (0, 0, 900) in the build's frame, and not beside the build

#### Scenario: Upright piece
- **WHEN** extra part `post` (qty 1, 900 × 45 mm) is placed with length along z and width along y
- **THEN** the board stands 900 mm tall, 45 mm deep and as thick as its slot in x

#### Scenario: Diagonal brace
- **WHEN** extra part `brace` (qty 1, 1000 × 60 mm, 18 mm slot) is placed at x 100, y 0, z 0, length along x, width along y, with tilt 30° towards z
- **THEN** the drawn brace's far end is 866 mm right of and 500 mm above its reference corner, its width still runs along y, and the overall height without an envelope includes it

#### Scenario: Rolled trim strip
- **WHEN** extra part `cove` (qty 1, 1200 × 40 mm) is placed with length along x and width along y, and `roll_deg` 45
- **THEN** the strip's width rises from its reference edge at 45° between y and z, and its length still runs along x

#### Scenario: Turned piece leaves the envelope
- **WHEN** the envelope is 1000 mm high and a placed piece 1200 mm long, length along x, with tilt 60° towards z, starts at z 0
- **THEN** the document is refused naming the part and saying it lies outside the envelope

#### Scenario: Tilt towards its own length axis
- **WHEN** a placement has length along x and tilt towards x
- **THEN** the document is refused naming `tilt.towards`

#### Scenario: Unplaced part unchanged
- **WHEN** a document has extra part `spare-trim` without `placements`
- **THEN** it is laid flat beside the build as before, and the build's overall size ignores it

#### Scenario: Placement count disagrees with quantity
- **WHEN** extra part `slat` has qty 4 and 3 placements
- **THEN** the document is refused naming `extra_parts[n].placements` and saying 4 are needed, and Blender is not started

#### Scenario: Placed piece outside the envelope
- **WHEN** the envelope is 1200 mm wide and a placed piece runs from x 300 for 1000 mm along x
- **THEN** the document is refused naming the part and saying it lies outside the envelope

#### Scenario: Cut list unchanged by placement
- **WHEN** the same document is derived with and without `placements` on its extra parts
- **THEN** both give the same cut-list rows, hardware lines and drilling list

### Requirement: An extra part can state angled end cuts
An extra part SHALL accept optional `end_cuts`, the same for every piece of the part:
- `across`: `width` or `thickness`, the side the ends are cut across;
- `start_deg` and `end_deg`, each −89 to 89, where 0 is a square end.

A positive angle shortens the edge opposite the reference edge by `size × tan(angle)`, where `size` is the width or thickness the cut runs across. A negative angle shortens the reference edge by the same amount. The stated `length` is always the longest edge, so the cut-list length is unchanged. Two cuts that shorten the same edge to zero or less SHALL be refused, naming the part. The same applies to one cut that shortens an edge to zero or less.

A build SHALL draw each piece of the part with its ends cut as stated, both when placed and when laid beside the build. The part's cut-list row SHALL carry the end cuts in its notes, for example "ends cut 35° / −35° across width". Its quantity, length, width, thickness and material SHALL stay unchanged.

#### Scenario: Brace cut to sit flush between posts
- **WHEN** extra part `brace` (1000 × 60 mm) has `end_cuts` across width with start 30° and end −30°, and is placed with length along x, width along z and tilt 30° towards z between two upright posts
- **THEN** the drawn brace is a parallelogram in its face whose ends stand plumb against the posts, and its cut-list row says "ends cut 30° / −30° across width" with length 1000

#### Scenario: Brace cut to sit flush on rails
- **WHEN** the same brace instead has start 60° and end −60° (90° less the tilt)
- **THEN** its ends lie level, flush with horizontal rails above and below

#### Scenario: Mitred frame member
- **WHEN** extra part `stile` (600 × 50 mm) has `end_cuts` across width with start 45° and end 45°
- **THEN** each piece is drawn as a trapezoid whose reference edge is 600 mm and whose opposite edge is 500 mm

#### Scenario: Cuts that consume the piece
- **WHEN** extra part `stub` (80 × 60 mm) has `end_cuts` across width with start 45° and end 45°
- **THEN** the document is refused naming `stub` and saying the end cuts leave no length

### Requirement: A protruding-shelf fit moves placed extra parts with the build
When a revision is fitted to a board that reaches in front of the build's front plane, every placed extra-part piece's `y` SHALL rise by the same amount as the modules and wall shelves, so the pieces stay where they sit on the build. The revision confirmation SHALL carry one fit line per moved part. Unplaced extra parts SHALL NOT change.

#### Scenario: Placed frame moves back with the cabinet
- **WHEN** module `cabinet` gets a shelf that protrudes 162 mm and extra part `top-frame` is placed at y 0
- **THEN** `cabinet`'s `y` and `top-frame`'s placement `y` both become 162, and the confirmation says `top-frame`'s pieces move back 162 mm
