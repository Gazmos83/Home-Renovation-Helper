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

Any item, of any type, MAY carry `hidden`. `hidden: true` marks an item that stays in the layout but is left out of the build and every render. `hidden: false` SHALL be accepted and stored as if the field were absent. Any other value SHALL be refused naming the item and `hidden`.

Every item SHALL be placed either against a wall (wall index and offset in millimetres) or free-standing (x and y in millimetres in the room's plan frame, and a rotation in degrees). In an apartment scope every item SHALL also name its room. The document MAY carry a `floor` finish that covers the whole floor of the room, or of every room of the apartment, following its outline whatever its shape. The finish SHALL state:
- `tile_width_mm` and `tile_length_mm`, whole millimetres from 20 to 2500; the width runs along the plan's x axis and the length along its y axis;
- `tile_colour` and `grout_colour`, each as `#rrggbb`;
- `grout_width_mm`, a number from 0 to 20, where 0 means butted tiles or planks with no visible joint;
- optionally `pattern`, either `"grid"` (the default: joints in line) or `"staggered"` (each row shifted by half a tile, as for planks).

Any other `floor` field SHALL be refused by name, and a value out of range SHALL be refused naming the field and its range. A document without `floor` keeps the default floor.

The document SHALL carry no output, frame, resolution or engine field. An unknown field anywhere SHALL be refused by name, and nothing is built.

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

#### Scenario: Hidden sofa accepted
- **WHEN** a stand-in `sofa` carries `hidden: true`
- **THEN** it is accepted, and its normalised form keeps `hidden: true`

#### Scenario: Hidden piece accepted
- **WHEN** the approved `listening-wall` v4 is placed as a `piece` with `hidden: true`
- **THEN** it is accepted, and its normalised form keeps `hidden: true`

#### Scenario: Hidden false is the same as no flag
- **WHEN** a library model `armchair` carries `hidden: false`
- **THEN** it is accepted, and its normalised form has no `hidden` field

#### Scenario: Hidden must be true or false
- **WHEN** a stand-in carries `hidden: "yes"`
- **THEN** it is refused naming the item and `hidden`, and nothing is built

#### Scenario: Tiled floor accepted
- **WHEN** a document for room `Wohnen` carries `floor: {tile_width_mm: 600, tile_length_mm: 600, tile_colour: "#e8e4dc", grout_colour: "#9a958c", grout_width_mm: 3}`
- **THEN** it is accepted, and its normalised form keeps the finish with `pattern: "grid"`

#### Scenario: Plank floor accepted
- **WHEN** the floor finish states 200 × 1200 mm tiles with `grout_width_mm: 0` and `pattern: "staggered"`
- **THEN** it is accepted

#### Scenario: Unknown floor field
- **WHEN** the floor finish carries `texture: "marble.png"`
- **THEN** it is refused naming `texture`, and nothing is built

#### Scenario: Tile too small
- **WHEN** the floor finish states `tile_width_mm: 5`
- **THEN** it is refused naming `tile_width_mm` and the range 20 to 2500

#### Scenario: Unknown pattern
- **WHEN** the floor finish states `pattern: "herringbone"`
- **THEN** it is refused naming `pattern` and the values `grid` and `staggered`

### Requirement: A composition is versioned and built headless
A confirmed composition SHALL be stored as a new version folder for its scope, holding the normalised document. That version SHALL be recorded as revised from the previous version, if any. Earlier versions SHALL never change. The build SHALL run in headless Blender under the one-process rule. It SHALL generate the room (or every room of the apartment) with its walls, openings, floor and ceiling. When the document carries a floor finish, every floor of the scope SHALL show it in stills and turntables: tiles of the stated size and colour, separated by joints of the grout width and colour, in the stated pattern, with the joint lines on multiples of the tile size from the plan's origin. The 3D view's `model.glb` and the screenshot SHALL show the floor in the tile colour, without the joints. It SHALL place each item that is not hidden: each piece from that version's built model, each stand-in as a box in its colour, and each model from the library, stretched to exactly its stated size on each axis. Every item SHALL stand on the floor, except a ceiling-layer stand-in or model, which SHALL hang with its highest point at the ceiling of its room. A hidden item SHALL NOT be placed, so it is absent from `model.blend`, `model.glb`, the screenshot and every render, restyle variant and detail pass made from the version. A room composition with no items, or with only hidden items, SHALL build the room alone. It SHALL publish `model.blend`, `model.glb`, a screenshot and a build report. The build report SHALL list each item's final size and the height of its lowest point above the floor, and, for each library model, its per-axis scale factors; for an empty room the report's item list is empty. For each placed item it SHALL also list the item's name (a piece's package id and version) and the mesh names in `model.glb` that belong to that item. A hidden item SHALL be listed with `hidden: true` and no size, height or meshes. The build report SHALL also hold a surface map. The surface map SHALL name every surface the owner can switch: each wall by its number (prefixed with its room's name for an apartment), the floor and the ceiling (per room for an apartment), and the items. For each surface it SHALL list the mesh names in `model.glb` that belong to it. A piece version that is not built SHALL fail the build naming that piece, unless the item is hidden; it SHALL never be built implicitly.

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

#### Scenario: Hidden sofa left out of the build
- **WHEN** `Wohnen` is built with a visible stand-in `table` and a hidden stand-in `sofa`
- **THEN** `model.glb` holds the table and no mesh of the sofa, and the report lists `sofa` with `hidden: true` and `table` with its name, size and meshes

#### Scenario: Only hidden items
- **WHEN** `Hall` is built with one item, which is hidden
- **THEN** the build succeeds with the room alone, and the report lists that item with `hidden: true`

#### Scenario: Item meshes listed
- **WHEN** `Wohnen` is built with a library model `armchair` and the piece `listening-wall` v4
- **THEN** the report lists `armchair` and `listening-wall v4` each with its own mesh names, every one of them is under the surface map's items, and no mesh is listed for two items

#### Scenario: Tiles across an L-shaped floor
- **WHEN** an L-shaped room `Wohnen` is built with a floor finish of 600 × 600 mm tiles
- **THEN** the whole floor, inner corner included, carries the tile material, and the build report states the finish

#### Scenario: Finish in the 3D view
- **WHEN** that version's `model.glb` is opened in the 3D view
- **THEN** the floor shows the tile colour

#### Scenario: No finish, default floor
- **WHEN** a document without `floor` is built
- **THEN** the floor has the default floor material, as before
