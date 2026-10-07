# room-composition Specification

## Purpose
Lets the owner put several approved pieces, stand-ins for bought furniture and imported models into one measured room, or a whole apartment, as a versioned spec document. The document is built headless and rendered only through the render guard, so a finished design can be seen in its real surroundings.

## Requirements

### Requirement: A composition document describes one room or one apartment
A room-composition document SHALL name exactly one scope: a house-file room by name (the default), or a house-file apartment by name, which covers all of its rooms. It SHALL list between one and the configured maximum number of items. Each item SHALL have a unique id and one of three types:
- `piece`: a package id and a version number;
- `stand-in`: a name, a width, depth and height in whole millimetres, and a colour as `#rrggbb`;
- `model`: a model-library id, a name, and a width, depth and height in whole millimetres.

Every item SHALL be placed either against a wall (wall index and offset in millimetres) or free-standing (x and y in millimetres in the room's plan frame, and a rotation in degrees). In an apartment scope every item SHALL also name its room. The document SHALL carry no output, frame, resolution or engine field. An unknown field anywhere SHALL be refused by name, and nothing is built.

#### Scenario: Room scope with three item types
- **WHEN** a document for room `Wohnen` lists the approved `listening-wall` v4 against wall 1 at offset 0, a stand-in `sofa` of 2200 × 950 × 800 mm in `#7a6a58`, and a library model `armchair` placed free-standing
- **THEN** it is accepted, and its normalised form lists the three items with their sizes and placements

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
A `piece` item SHALL be refused, naming the package and version, when that version is not approved at the time the composition is proposed. A version unapproved after it was placed SHALL stay in the composition. Every read of the composition SHALL then report it as "no longer approved", and so SHALL the reply that starts a build or a render. It SHALL NOT be removed or replaced silently.

#### Scenario: Unapproved version refused
- **WHEN** the owner asks to place `listening-wall` v3, which is not approved
- **THEN** the proposal is refused saying v3 is not approved and naming the approved versions, if any

#### Scenario: Unapproved after placement
- **WHEN** `listening-wall` v4 is placed in `Wohnen` v2 and the owner then unapproves v4
- **THEN** `Wohnen` v2 still lists v4, marked "no longer approved", in the Studio, in the house note and in the next render's reply

### Requirement: A composition is versioned and built headless
A confirmed composition SHALL be stored as a new version folder for its scope, holding the normalised document. That version SHALL be recorded as revised from the previous version, if any. Earlier versions SHALL never change. The build SHALL run in headless Blender under the one-process rule. It SHALL generate the room (or every room of the apartment) with its walls, openings, floor and ceiling. It SHALL place each piece from that version's built model, each stand-in as a box in its colour, and each model from the library, stretched to exactly its stated size on each axis and standing on the floor. It SHALL publish `model.blend`, a screenshot and a build report that lists each item's final size and, for each library model, its per-axis scale factors. A piece version that is not built SHALL fail the build naming that piece; it SHALL never be built implicitly.

#### Scenario: Build of a three-item room
- **WHEN** the owner confirms `Wohnen` with one approved piece, one stand-in and one model
- **THEN** a new version folder holds the document, `model.blend`, a screenshot and a report naming the three items with their sizes, and the version's status reads `succeeded`

#### Scenario: Piece not built
- **WHEN** a placed piece version has no successful build
- **THEN** the composition build fails naming that piece and version, and no `model.blend` is published

#### Scenario: Model scaled
- **WHEN** a library model measured at 0.9 × 0.8 × 1.0 m is placed with a stated size of 800 × 700 × 900 mm
- **THEN** it is stretched to exactly 800 × 700 × 900 mm, its lowest point rests on the floor, and the build report states its per-axis scale factors

### Requirement: A composition renders only through the guard
A still or turntable of a composition version SHALL go through the render guard exactly as a piece or a shell does: a tier is required, raw frame, resolution and engine values are refused by name, the estimate is stated before the run, and `final` runs only after the owner's `yes`. Output SHALL be published atomically in the composition version's folder, in the same `still.png`, `frames/`, `viewer.html` and `scene.json` layout. For a turntable, walls between the camera and the room SHALL be hidden per frame. A room scope SHALL be the default. An apartment scope SHALL be rendered only when the composition's scope is an apartment.

#### Scenario: Draft turntable of a room
- **WHEN** a `draft` turntable of `Wohnen` v2 is requested
- **THEN** 12 frames at 600 × 600 on Eevee are published under that version, and `scene.json` records the tier and the composition document

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
