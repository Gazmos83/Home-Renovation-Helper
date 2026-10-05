## MODIFIED Requirements

### Requirement: The room-scene document's output is tier-driven
A room-scene document SHALL describe the room (corners, height, wall thickness), openings, where the piece is placed, existing furnishings, and `output.kind` of `still` or `turntable` only. A document naming `output.frames`, `output.resolution` or any other output field SHALL be refused by field name. The room's outline SHALL be a simple polygon of three to twelve corners, convex or not. Room geometry SHALL be validated as before: a piece overflowing its wall or the ceiling, a footprint leaving the room (including across the inner corner of an L-shaped room), an opening off its wall, a door with a sill, a self-intersecting outline, duplicate furnishing names and a furnishing intersecting the piece are each refused naming the problem.

#### Scenario: Frames in the document
- **WHEN** a room-scene document carries `output: {kind: turntable, frames: 36}`
- **THEN** it is refused naming `frames`

#### Scenario: Overflow named
- **WHEN** the piece is wider than the remaining length of its wall
- **THEN** the document is refused naming the wall and the excess in millimetres

#### Scenario: L-shaped room draft still
- **WHEN** a `draft` still is requested of a piece placed on a wall of a six-corner L-shaped room
- **THEN** the still is rendered with the floor and ceiling following the L and the camera aimed at a point inside the room

#### Scenario: Footprint across the inner corner
- **WHEN** a piece placed in an L-shaped room would reach past the inner corner into the missing quarter
- **THEN** the document is refused naming the footprint leaving the room
