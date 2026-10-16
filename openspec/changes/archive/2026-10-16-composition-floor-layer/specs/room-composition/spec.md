## MODIFIED Requirements

### Requirement: A composition document describes one room or one apartment
A room-composition document SHALL name exactly one scope: a house-file room by name (the default), or a house-file apartment by name, which covers all of its rooms. A room scope SHALL list between zero and the configured maximum number of items; zero items means the room alone, with no furniture. An apartment scope SHALL list between one and the configured maximum number of items. Each item SHALL have a unique id and one of three types:
- `piece`: a package id and a version number;
- `stand-in`: a name, a width, depth and height in whole millimetres, and a colour as `#rrggbb`;
- `model`: a model-library id, a name, and a width, depth and height in whole millimetres.

A `stand-in` or a `model` MAY carry `layer: "floor"`, marking an item that lies flat on the floor, such as a rug or a mat. Any other `layer` value SHALL be refused naming the item and the field. A `piece` SHALL NOT carry `layer`; it is refused as an unknown field. A floor-layer item SHALL be at most 30 mm tall; a taller one SHALL be refused naming the item and the 30 mm limit. An item without `layer` is a standing item.

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

### Requirement: Every item is placed validly
Each item SHALL be checked against its room. A piece's size SHALL be the overall size of that version. A stand-in's and a model's size SHALL be the size stated in the document. An item SHALL be refused, naming its id and the problem, when it:
- leaves the room's outline (including across the inner corner of an L-shaped room);
- is taller than the ceiling;
- runs past the end of its wall;
- stands in front of a door;
- stands in front of a window and is taller than its sill;
- overlaps another item's footprint.

A floor-layer item SHALL be exempt from the door and window checks, and its footprint SHALL be allowed to overlap a standing item's footprint. Two floor-layer items that overlap SHALL be refused, and so SHALL two standing items that overlap.

Placement rules configured in the design rules SHALL be applied to every standing item, and not to floor-layer items. A `refuse` breach SHALL refuse the document, naming the rule. A `warn` breach SHALL be reported with the result.

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
