## MODIFIED Requirements

### Requirement: A build publishes the package files and a screenshot
A successful build SHALL publish the following into the version folder, all at once:
- `model.glb`, `model.blend`, `spec.json`, `cutlist.csv` and `hardware.csv`;
- `screenshot.png`, `front.png`, `side.png` and `top.png`.

Every file SHALL be non-empty and parseable as its format.

The emitted `spec.json` SHALL carry:
- `overall` (width, height, depth in mm);
- `modules` (each module's size and position);
- `layers` (each exported mesh under exactly one of `carcass`, `backs`, `shelves`, `fronts`, `extras`, `handles`; a layer with no meshes is omitted);
- `parts`, `hardware`, `assembly` and `blender_version`.

The build SHALL export one object per cut-list piece, named by its cut-list id, and one object per modelled handle, as set out in "A front can carry a modelled handle"; each is parented to one empty per module.

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


## ADDED Requirements

### Requirement: A front can carry a modelled handle
A door, drawer or flap entry SHALL accept an optional `handle`, with these fields:
- `kind`: `bar` or `knob`.
- `length`: a bar's length in mm. It is required for a bar and refused on a knob.
- `orientation`: `vertical` or `horizontal`. Bars only, refused on a knob. Doors default to `vertical`; drawers and flaps to `horizontal`.
- `edge`: doors only, refused on drawers and flaps. `meeting`, `left` or `right`. `meeting` puts the handles of each pair of leaves, counted from the left, on the edge the pair shares, and needs an even count. The default is `meeting` for an even count, else `right`.
- `inset_mm`: the distance from the leaf's handle edge to the handle's centre line. The handle edge is the edge `edge` names for a door, the top edge for a drawer, and the edge opposite the hinge for a flap. Doors and flaps default to 40 mm; a drawer's handle defaults to the middle of the leaf's height.
- `at_mm`: the handle's centre along that edge. For a door it is measured from the leaf's bottom edge; for a drawer or flap, from the leaf's left edge. The default is the middle of the leaf along that edge.
- `finish`: `black`, `aluminium`, `steel` or `brass`. The default is `black`.
- `key`: an optional hardware key, as for a hinge. The default is `handle-bar-<length>-<finish>` for a bar and `handle-knob-<finish>` for a knob.

One `handle` SHALL serve every leaf of its entry. An unknown handle field SHALL be refused by name, as any unknown field is.

A handle SHALL be refused, naming its entry's `handle` and with nothing built, when:
- it is on a push-latch door;
- its `edge` is `meeting` on an odd count;
- it is on a module with `side_folds`, which this change does not support;
- it does not lie at least 10 mm inside its leaf on every side; the refusal gives the leaf's size.

A built version SHALL draw, for each leaf with a handle, one handle object in front of that leaf at its stated place:
- a bar is a 12 mm bar of the stated length, standing 30 mm proud of the front on two posts;
- a knob is a 30 mm round knob, 25 mm proud;
- each is coloured by its finish.

Each handle object SHALL be named `<front row id>-handle`, with `#<n>` for further leaves. The front row id is the door, drawer-front or flap row it sits on. It SHALL be listed in the `handles` layer and parented to its module's empty, so it moves with its module in the exploded view. A handle SHALL NOT be a cut-list row. It SHALL NOT change `overall`, and SHALL NOT count in the envelope check.

The hardware SHALL hold one line per handle key, with one handle per leaf that carries it. The item text names the kind, the length for a bar, and the finish, for example "Bar handle 900 mm, black". The note reads "Rule: one handle per leaf". A door row's note SHALL name its handle's key instead of "handle as specified". Hardware lines written by hand SHALL be kept as written. A front without `handle` SHALL be drawn, derived and listed exactly as before. Handles SHALL add nothing to the drilling list.

#### Scenario: Bar handles on a pair of doors
- **WHEN** module `left-wardrobe`, 900 × 2034 mm, has one entry of two hinged doors with a vertical 900 mm black bar handle and no `edge`
- **THEN** the build draws `left-wardrobe-door-1-handle` and `left-wardrobe-door-1-handle#2`, each 40 mm from the edge the two doors share and centred on the doors' height, in the `handles` layer, and the hardware holds `handle-bar-900-black` ×2 "Bar handle 900 mm, black"

#### Scenario: Drawer handles
- **WHEN** an entry of five drawers carries a horizontal 160 mm bar handle with `inset_mm` 30
- **THEN** each of the five drawer fronts gets a handle centred across its width with its centre line 30 mm below its top edge, and the hardware holds that handle's key ×5

#### Scenario: Handle on a push-latch door refused
- **WHEN** a push-latch door entry carries a handle
- **THEN** the spec is refused naming that entry's `handle` and saying a push-latch door takes no handle

#### Scenario: Handle too long for its leaf
- **WHEN** a drawer 450 mm wide carries a horizontal 500 mm bar handle
- **THEN** the spec is refused naming that entry's `handle` and the drawer front's size, and nothing is built

#### Scenario: Handle on a folded module refused
- **WHEN** a module with a left side fold has a door entry with a handle
- **THEN** the spec is refused naming that entry's `handle` and saying handles on a folded module are not supported

#### Scenario: Fronts without handles unchanged
- **WHEN** a version without any `handle` is rebuilt
- **THEN** its cut list, hardware and exported objects equal the previous build's, and `spec.json` has no `handles` layer

#### Scenario: Handles are not cut
- **WHEN** a version with handles is built
- **THEN** `cutlist.csv` holds no handle row, `overall` equals that of the same version without handles, and `spec.json` lists every handle object in the `handles` layer only
