## MODIFIED Requirements

### Requirement: A composition document describes one room or one apartment
A room-composition document SHALL name exactly one scope: a house-file room by name (the default), or a house-file apartment by name, which covers all of its rooms. A room scope SHALL list between zero and the configured maximum number of items; zero items means the room alone, with no furniture. An apartment scope SHALL list between one and the configured maximum number of items. Each item SHALL have a unique id and one of three types:
- `piece`: a package id and a version number;
- `stand-in`: a name, a width, depth and height in whole millimetres, and a colour as `#rrggbb`;
- `model`: a model-library id, a name, and a width, depth and height in whole millimetres.

A `stand-in` or a `model` MAY carry a `layer`:
- `layer: "floor"` marks an item that lies flat on the floor, such as a rug or a mat. A floor-layer item SHALL be at most 30 mm tall; a taller one SHALL be refused naming the item and the 30 mm limit.
- `layer: "ceiling"` marks an item that hangs from the ceiling, such as a pendant lamp. Its stated height SHALL be measured from the ceiling down to its lowest point, including any cable and canopy.

Any other `layer` value SHALL be refused naming the item and the field. A `piece` SHALL NOT carry `layer`; it is refused as an unknown field. An item without `layer` is a standing item.

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

#### Scenario: Floor-layer rug accepted
- **WHEN** a stand-in `rug` of 2300 × 1600 × 10 mm carries `layer: "floor"`
- **THEN** it is accepted, and its normalised form keeps `layer: "floor"`

#### Scenario: Unknown layer value
- **WHEN** a stand-in carries `layer: "wall"`
- **THEN** it is refused naming the item and `layer`, and nothing is built

#### Scenario: Floor layer on a piece
- **WHEN** a `piece` item carries `layer: "floor"`
- **THEN** it is refused naming `layer` as an unknown field

#### Scenario: Floor-layer item too tall
- **WHEN** a stand-in of 40 mm height carries `layer: "floor"`
- **THEN** it is refused naming the item and the 30 mm limit

#### Scenario: Ceiling-layer pendant accepted
- **WHEN** a library model `pendant` of 500 × 500 × 1100 mm carries `layer: "ceiling"`
- **THEN** it is accepted, and its normalised form keeps `layer: "ceiling"`

#### Scenario: Ceiling layer on a piece
- **WHEN** a `piece` item carries `layer: "ceiling"`
- **THEN** it is refused naming `layer` as an unknown field

### Requirement: Every item is placed validly
Each item SHALL be checked against its room. A piece's size SHALL be the overall size of that version. A stand-in's and a model's size SHALL be the size stated in the document. An item SHALL be refused, naming its id and the problem, when it:
- leaves the room's outline (including across the inner corner of an L-shaped room);
- is taller than the ceiling;
- runs past the end of its wall;
- stands in front of a door;
- stands in front of a window and is taller than its sill;
- overlaps another item's footprint.

A floor-layer item SHALL be exempt from the door and window checks, and its footprint SHALL be allowed to overlap a standing item's footprint. Two floor-layer items that overlap SHALL be refused, and so SHALL two standing items that overlap.

A ceiling-layer item SHALL hang with its top at the ceiling of its room. It SHALL fill the height from the ceiling height minus its stated height up to the ceiling. A standing or floor-layer item SHALL fill the height from the floor up to its stated height. When a ceiling-layer item's footprint overlaps another item's footprint, the two items SHALL be refused, naming both ids, only when their height ranges overlap. A lamp whose lowest point is exactly at the top of a table below it is accepted. Two ceiling-layer items whose footprints overlap are therefore always refused. A ceiling-layer item SHALL take the door and window checks only when its lowest point is below the top of the opening (sill plus opening height).

Placement rules configured in the design rules SHALL be applied to every standing item, and not to floor-layer or ceiling-layer items. A `refuse` breach SHALL refuse the document, naming the rule. A `warn` breach SHALL be reported with the result.

#### Scenario: Two items overlap
- **WHEN** the stand-in `sofa` and the model `armchair` have overlapping footprints
- **THEN** the document is refused naming both ids

#### Scenario: Blocks a door
- **WHEN** a stand-in is placed against wall 0 across the hallway door's width
- **THEN** it is refused naming the item, the door and its wall

#### Scenario: L-shaped room
- **WHEN** a free-standing item in an L-shaped room would reach into the missing quarter
- **THEN** it is refused naming the item as leaving the room

#### Scenario: Rug under the sofa
- **WHEN** the floor-layer stand-in `rug` lies partly under the standing stand-in `grey-sofa`
- **THEN** the document is accepted

#### Scenario: Two rugs overlap
- **WHEN** two floor-layer items have overlapping footprints
- **THEN** the document is refused naming both ids

#### Scenario: Rug in front of a door
- **WHEN** a floor-layer stand-in lies in front of the hallway door
- **THEN** it is accepted, and no door-swing placement rule is reported for it

#### Scenario: Floor-layer item still inside the room
- **WHEN** a floor-layer item reaches past the room's outline
- **THEN** it is refused naming the item as leaving the room

#### Scenario: Pendant over the table
- **WHEN** in a room with a 2500 mm ceiling, the ceiling-layer model `pendant` of 500 × 500 × 1100 mm hangs over the standing stand-in `table` of 1600 × 900 × 750 mm
- **THEN** the document is accepted, because the pendant reaches down to 1400 mm and the table up to 750 mm

#### Scenario: Pendant hangs into a cabinet
- **WHEN** in a room with a 2500 mm ceiling, the ceiling-layer model `pendant` of 500 × 500 × 1100 mm hangs over a standing stand-in `cabinet` of 600 × 400 × 1600 mm
- **THEN** the document is refused naming both ids

#### Scenario: Two pendants overlap
- **WHEN** two ceiling-layer items have overlapping footprints
- **THEN** the document is refused naming both ids

#### Scenario: Pendant above a door
- **WHEN** in a room with a 2500 mm ceiling, a ceiling-layer stand-in of 400 × 400 × 300 mm hangs in front of a 2000 mm high door
- **THEN** it is accepted, and no door-swing placement rule is reported for it

#### Scenario: Long pendant in front of a door
- **WHEN** in a room with a 2500 mm ceiling, a ceiling-layer stand-in of 400 × 400 × 1100 mm hangs in front of a 2000 mm high door
- **THEN** it is refused naming the item, the door and its wall

#### Scenario: Ceiling-layer item longer than the room is high
- **WHEN** a ceiling-layer item's stated height is greater than its room's ceiling height
- **THEN** it is refused naming the item as taller than the ceiling

#### Scenario: Ceiling-layer item still inside the room
- **WHEN** a ceiling-layer item reaches past the room's outline
- **THEN** it is refused naming the item as leaving the room

### Requirement: A composition is versioned and built headless
A confirmed composition SHALL be stored as a new version folder for its scope, holding the normalised document. That version SHALL be recorded as revised from the previous version, if any. Earlier versions SHALL never change. The build SHALL run in headless Blender under the one-process rule. It SHALL generate the room (or every room of the apartment) with its walls, openings, floor and ceiling. It SHALL place each piece from that version's built model, each stand-in as a box in its colour, and each model from the library, stretched to exactly its stated size on each axis. Every item SHALL stand on the floor, except a ceiling-layer stand-in or model, which SHALL hang with its highest point at the ceiling of its room. A room composition with no items SHALL build the room alone. It SHALL publish `model.blend`, `model.glb`, a screenshot and a build report. The build report SHALL list each item's final size and the height of its lowest point above the floor, and, for each library model, its per-axis scale factors; for an empty room the report's item list is empty. The build report SHALL also hold a surface map. The surface map SHALL name every surface the owner can switch: each wall by its number (prefixed with its room's name for an apartment), the floor and the ceiling (per room for an apartment), and the items. For each surface it SHALL list the mesh names in `model.glb` that belong to it. A piece version that is not built SHALL fail the build naming that piece; it SHALL never be built implicitly.

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


#### Scenario: Ceiling-layer model hangs from the ceiling
- **WHEN** `Wohnen`, with a 2500 mm ceiling, is built with the ceiling-layer library model `pendant` stated at 500 × 500 × 1100 mm
- **THEN** the pendant is stretched to exactly 500 × 500 × 1100 mm, its highest point is at 2500 mm, and the build report states its lowest point at 1400 mm

#### Scenario: Ceiling-layer stand-in in an apartment room
- **WHEN** an apartment is built with a ceiling-layer stand-in of 300 mm height in `Bad`, whose ceiling is 2400 mm while the apartment ceiling is 2550 mm
- **THEN** the stand-in's lowest point is at 2100 mm and its highest point at 2400 mm
