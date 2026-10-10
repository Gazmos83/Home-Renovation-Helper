# room-composition Specification

## Purpose
Lets the owner put several approved pieces, stand-ins for bought furniture and imported models into one measured room, or a whole apartment, as a versioned spec document. The document is built headless and rendered only through the render guard, so a finished design can be seen in its real surroundings.

## Requirements

### Requirement: A composition document describes one room or one apartment
A room-composition document SHALL name exactly one scope: a house-file room by name (the default), or a house-file apartment by name, which covers all of its rooms. A room scope SHALL list between zero and the configured maximum number of items; zero items means the room alone, with no furniture. An apartment scope SHALL list between one and the configured maximum number of items. Each item SHALL have a unique id and one of three types:
- `piece`: a package id and a version number;
- `stand-in`: a name, a width, depth and height in whole millimetres, and a colour as `#rrggbb`;
- `model`: a model-library id, a name, and a width, depth and height in whole millimetres.

Every item SHALL be placed either against a wall (wall index and offset in millimetres) or free-standing (x and y in millimetres in the room's plan frame, and a rotation in degrees). In an apartment scope every item SHALL also name its room. The document SHALL carry no output, frame, resolution or engine field. An unknown field anywhere SHALL be refused by name, and nothing is built.

#### Scenario: Room scope with three item types
- **WHEN** a document for room `Wohnen` lists the approved `listening-wall` v4 against wall 1 at offset 0, a stand-in `sofa` of 2200 × 950 × 800 mm in `#7a6a58`, and a library model `armchair` placed free-standing
- **THEN** it is accepted, and its normalised form lists the three items with their sizes and placements

#### Scenario: Empty room
- **WHEN** a document for room `Hall` lists no items
- **THEN** it is accepted, and its normalised form holds the room `Hall` and an empty item list

#### Scenario: Empty apartment refused
- **WHEN** a document for apartment `Wohnung` lists no items
- **THEN** it is refused saying an apartment composition needs at least one item, and nothing is built

#### Scenario: Output field refused
- **WHEN** a composition document carries `output: {frames: 36}`
- **THEN** it is refused naming `output` and nothing is built

#### Scenario: Unknown room
- **WHEN** the document names a room the house file does not hold
- **THEN** it is refused naming the room and listing the rooms that exist

#### Scenario: Apartment item without a room
- **WHEN** an apartment-scope document has an item that names no room
- **THEN** it is refused naming that item's id

### Requirement: Every item is placed validly
Each item SHALL be checked against its room. A piece's size SHALL be the overall size of that version. A stand-in's and a model's size SHALL be the size stated in the document. An item SHALL be refused, naming its id and the problem, when it:
- leaves the room's outline (including across the inner corner of an L-shaped room);
- is taller than the ceiling;
- runs past the end of its wall;
- stands in front of a door;
- stands in front of a window and is taller than its sill;
- overlaps another item's footprint.

Placement rules configured in the design rules SHALL be applied to every item. A `refuse` breach SHALL refuse the document, naming the rule. A `warn` breach SHALL be reported with the result.

#### Scenario: Two items overlap
- **WHEN** the stand-in `sofa` and the model `armchair` have overlapping footprints
- **THEN** the document is refused naming both ids

#### Scenario: Blocks a door
- **WHEN** a stand-in is placed against wall 0 across the hallway door's width
- **THEN** it is refused naming the item, the door and its wall

#### Scenario: L-shaped room
- **WHEN** a free-standing item in an L-shaped room would reach into the missing quarter
- **THEN** it is refused naming the item as leaving the room

### Requirement: Only approved piece versions are placed
A `piece` item SHALL be refused, naming the package and version, when that version is not approved at the time the composition is proposed. A version unapproved after it was placed SHALL stay in the composition when that composition version is not approved. Every read of the composition SHALL then report it as "no longer approved", and so SHALL the reply that starts a build or a render. It SHALL NOT be removed or replaced silently.

Unapproving a piece version that is placed in an approved composition version SHALL be refused, naming the composition and its version, until that composition version is unapproved. The piece SHALL stay approved.

#### Scenario: Unapproved version refused
- **WHEN** the owner asks to place `listening-wall` v3, which is not approved
- **THEN** the proposal is refused saying v3 is not approved and naming the approved versions, if any

#### Scenario: Unapproved after placement
- **WHEN** `listening-wall` v4 is placed in `Wohnen` v2, `Wohnen` v2 is not approved, and the owner then unapproves v4
- **THEN** `Wohnen` v2 still lists v4, marked "no longer approved", in the Studio, in the house note and in the next render's reply

#### Scenario: Unapprove refused while the room is approved
- **WHEN** `listening-wall` v4 is placed in approved `Wohnen` v2 and the owner unapproves v4
- **THEN** the request is refused naming `Wohnen` version 2, v4 stays approved, and `Wohnen` v2 is unchanged

### Requirement: The owner approves and unapproves a built composition version
The owner SHALL be able to approve one version of a composition and to unapprove it through owner-gated routes on that version. Approval SHALL be refused with a 409 and a stated reason when the version's build has not succeeded, when the version is not recorded, or when any placed piece version is not currently approved (naming those pieces). An unknown composition or version SHALL answer 404. Approving a version SHALL clear the approval of any other version of the same composition; approving an approved version or unapproving an unapproved one SHALL succeed and change nothing. A new composition version SHALL start unapproved. Reading a composition SHALL report which version is approved, or none. No model tool SHALL approve or unapprove a composition version.

#### Scenario: Approve a built room version
- **WHEN** the owner approves `Wohnen` version 2 whose build succeeded and whose placed pieces are currently approved
- **THEN** reading `Wohnen` reports version 2 approved with the time, and no other version of `Wohnen` is approved

#### Scenario: Unapprove a room version
- **WHEN** the owner unapproves the approved `Wohnen` version 2
- **THEN** reading it reports no version of `Wohnen` approved

#### Scenario: Unapproved pieces refuse room approval
- **WHEN** `Wohnen` version 2 places `listening-wall` v4 and v4 is not approved, and the owner approves version 2
- **THEN** the request is refused with a 409 naming `listening-wall` v4, and version 2 stays unapproved

#### Scenario: Not built yet
- **WHEN** the owner approves `Wohnen` version 3 while its build is `running`
- **THEN** the request is refused with a 409 saying the version must be built first, and nothing changes

#### Scenario: Without a login
- **WHEN** the composition approve route is called without the owner's session
- **THEN** it answers 401 and nothing changes

### Requirement: A composition version can be deleted
The owner SHALL be able to delete one version of a composition. Deleting SHALL remove the version's folder with everything in it: the input, the model, the screenshot, the renders and the viewer. The service SHALL refuse the delete, without changing anything, and say why in plain words when:
- the version is approved ("unapprove version N first");
- its build or one of its renders is queued or running;
- the version does not exist.

Deleting the only remaining version of a composition SHALL delete the composition. The measured room SHALL stay. Version numbers SHALL never be reused. After a deletion, the next version of the composition SHALL be numbered one above the highest version it ever had, whether or not that version still exists. Deleting is an owner route only; no agent tool SHALL delete a composition version.

#### Scenario: Delete an older version
- **WHEN** `Wohnen` has versions 1 to 4, version 4 is approved, and the owner deletes version 2
- **THEN** `Wohnen/v2/` no longer exists, versions 1, 3 and 4 are unchanged, and version 4 stays approved

#### Scenario: Approved version refused
- **WHEN** the owner deletes `Wohnen` version 4 while it is approved
- **THEN** the delete is refused saying to unapprove version 4 first, and nothing is removed

#### Scenario: Version still building
- **WHEN** the owner deletes a composition version whose build is running
- **THEN** the delete is refused saying the version is still building

#### Scenario: Numbers are not reused
- **WHEN** `Wohnen` has versions 1 to 3, the owner deletes version 3 and then confirms a new compose
- **THEN** the new version is version 4

#### Scenario: Last version deletes the composition
- **WHEN** `Wohnen` has only version 1 and the owner deletes it
- **THEN** composition `Wohnen` is no longer listed and the measured room `Wohnen` is unchanged

### Requirement: A composition is versioned and built headless
A confirmed composition SHALL be stored as a new version folder for its scope, holding the normalised document. That version SHALL be recorded as revised from the previous version, if any. Earlier versions SHALL never change. The build SHALL run in headless Blender under the one-process rule. It SHALL generate the room (or every room of the apartment) with its walls, openings, floor and ceiling. It SHALL place each piece from that version's built model, each stand-in as a box in its colour, and each model from the library, stretched to exactly its stated size on each axis and standing on the floor. A room composition with no items SHALL build the room alone. It SHALL publish `model.blend`, `model.glb`, a screenshot and a build report. The build report SHALL list each item's final size and, for each library model, its per-axis scale factors; for an empty room the report's item list is empty. The build report SHALL also hold a surface map. The surface map SHALL name every surface the owner can switch: each wall by its number (prefixed with its room's name for an apartment), the floor and the ceiling (per room for an apartment), and the items. For each surface it SHALL list the mesh names in `model.glb` that belong to it. A piece version that is not built SHALL fail the build naming that piece; it SHALL never be built implicitly.

#### Scenario: Build of a three-item room
- **WHEN** the owner confirms `Wohnen` with one approved piece, one stand-in and one model
- **THEN** a new version folder holds the document, `model.blend`, `model.glb`, a screenshot and a report naming the three items with their sizes, and the version's status reads `succeeded`

#### Scenario: Build of an empty room
- **WHEN** the owner confirms `Hall` with no items
- **THEN** a new version folder holds the document, `model.blend` and `model.glb` with the room's walls, openings, floor and ceiling and no item, a screenshot and a report with an empty item list, and the version's status reads `succeeded`

#### Scenario: Surface map
- **WHEN** `Hall` is a four-walled room and its composition build succeeds
- **THEN** the report's surface map names wall 1 to wall 4, the floor, the ceiling and the items, and every mesh in `model.glb` belongs to exactly one of them

#### Scenario: Piece not built
- **WHEN** a placed piece version has no successful build
- **THEN** the composition build fails naming that piece and version, and no `model.blend` or `model.glb` is published

#### Scenario: Model scaled
- **WHEN** a library model measured at 0.9 × 0.8 × 1.0 m is placed with a stated size of 800 × 700 × 900 mm
- **THEN** it is stretched to exactly 800 × 700 × 900 mm, its lowest point rests on the floor, and the build report states its per-axis scale factors

### Requirement: A composition renders only through the guard
A still or turntable of a composition version SHALL go through the render guard exactly as a piece or a shell does: a tier is required, raw frame, resolution and engine values are refused by name, the estimate is stated before the run, and `final` runs only after the owner's `yes`. An empty room composition SHALL follow the same rules. Output SHALL be published atomically in the composition version's folder, in the same `still.png`, `frames/`, `viewer.html` and `scene.json` layout. For a turntable, walls between the camera and the room SHALL be hidden per frame. A room scope SHALL be the default. An apartment scope SHALL be rendered only when the composition's scope is an apartment.

#### Scenario: Draft turntable of a room
- **WHEN** a `draft` turntable of `Wohnen` v2 is requested
- **THEN** 12 frames at 600 × 600 on Eevee are published under that version, and `scene.json` records the tier and the composition document

#### Scenario: Draft still of an empty room
- **WHEN** a `draft` still of the empty `Hall` v1 is requested
- **THEN** the estimate is stated, a 600 × 600 Eevee still of the room alone is published under that version, and `scene.json` records the tier and an empty item list

#### Scenario: Final needs yes
- **WHEN** a `final` still of a composition is requested
- **THEN** a confirmation with the estimate is pending and nothing has started

#### Scenario: Raw resolution refused
- **WHEN** the render request carries `resolution: 4000`
- **THEN** it is refused naming `resolution` and no process starts

### Requirement: The detail pass may work on a composition
The detail pass SHALL accept a built composition version as its target under the same rules as a piece version:
- it starts only after the owner's confirmation;
- it works on a copy, `detail/detail.blend`;
- every script passes the allow-list;
- progress is checked with screenshots;
- a detail render is `final` only and needs the owner's approval;
- nothing is written back to the composition document.

#### Scenario: Lighting a room
- **WHEN** the owner confirms a detail pass on `Wohnen` v2
- **THEN** `Wohnen/v2/detail/detail.blend` is a copy of its `model.blend`, the live Blender has it open, and the composition document is byte-identical to before

### Requirement: A composition version's room dimensions can be read
The owner SHALL be able to read, for one composition version, the dimensions of its room plan, derived only from that version's stored document, so they never change after the version is made. The read SHALL list every unique wall once, with its surface label as in the surface map (`wall <n>` for a room, `<room>: wall <n>` for an apartment), its two plan end points and its length in millimetres; a wall two rooms of an apartment share SHALL be listed once. It SHALL list each room's ceiling height in millimetres with the room's name and a plan point inside that room. The composition list SHALL name each listed version's dimensions by their composition route when the version has `model.glb`. An unknown composition or version, or a version whose document cannot be read, SHALL answer not found. The read SHALL contain no file-system path.

#### Scenario: Room walls
- **WHEN** the owner reads the dimensions of `Wohnen` v2, whose plan has corners (0,0), (6200,0), (6200,5700), (3500,5700) and (1289,6064) and a 2500 mm ceiling
- **THEN** walls 1 to 5 are listed with lengths 6200, 5700, 2700, 2241 and 6199 mm (rounded to whole millimetres) and one ceiling of 2500 mm for `Wohnen`

#### Scenario: Apartment shared wall and heights
- **WHEN** the owner reads the dimensions of an apartment version where `Bad` and `Flur` share one wall and `Bad` is 2400 mm high while the apartment ceiling is 2550 mm
- **THEN** the shared wall is listed once, `Bad` has a 2400 mm ceiling and every other room 2550 mm

#### Scenario: Unknown version
- **WHEN** the owner reads the dimensions of a version that does not exist
- **THEN** the answer is not found
