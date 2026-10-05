## MODIFIED Requirements

### Requirement: Rooms are recorded with their measurements
The house file SHALL hold each room by name with its polygon (corners in millimetres, three to twelve, normalised counter-clockwise, forming a simple polygon — convex or not), ceiling height, wall thickness and openings (wall, type door or window, offset, width, height, sill), and optionally the apartment it belongs to, in whose plan frame its corners then lie. A room SHALL be validated like a room-scene document before it is stored: a self-intersecting outline, a repeated corner, an edge shorter than 50 mm, an opening off its wall or above the ceiling, or a door with a sill is refused naming the problem. A room name SHALL be unique.

#### Scenario: A room is stored
- **WHEN** Intake's confirmed numbers describe the living room as a 4000 × 3500 mm rectangle, 2600 mm high, with one door on wall 1
- **THEN** the house file holds that room and a later turn can read it by name

#### Scenario: An L-shaped room is stored
- **WHEN** a room is described by six corners forming an L
- **THEN** the house file holds it with its six corners counter-clockwise

#### Scenario: An impossible room is refused
- **WHEN** a room is submitted whose door carries a sill
- **THEN** it is refused naming the opening and nothing is stored

#### Scenario: A self-intersecting outline is refused
- **WHEN** a room's corners cross themselves (a bow-tie)
- **THEN** it is refused naming the outline and nothing is stored
