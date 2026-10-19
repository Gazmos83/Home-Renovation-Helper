## ADDED Requirements

### Requirement: A build notice warns when the piece is too big for its room
When a piece version builds successfully and the piece is recorded in a room, the application SHALL compare the version's overall size with that room, with no model call. When the version is taller than the room's ceiling, or wider than the room's longest wall, the build notice SHALL add one plain sentence per finding that names the room, the piece's figure and the room's figure in millimetres. The warning SHALL NOT stop the build, change the version, or refuse a later approval, placement or render. A piece with no room, or a failed build, SHALL get no warning.

#### Scenario: Taller than the ceiling
- **WHEN** `hochschrank` v2 (600 × 400 × 2600 mm) builds and its room `Wohnen` has a 2500 mm ceiling
- **THEN** the build notice reads "hochschrank version 2 is built. Too big for Wohnen: 2600 mm tall, the ceiling is 2500 mm."

#### Scenario: Wider than the longest wall
- **WHEN** a version 4200 mm wide builds and its room's longest wall is 4000 mm
- **THEN** the build notice adds "Too big for <room>: 4200 mm wide, the longest wall is 4000 mm."

#### Scenario: Fits
- **WHEN** a version 1200 × 400 × 900 mm builds in a room with a 2500 mm ceiling and a 4000 mm longest wall
- **THEN** the build notice is the usual "is built." sentence alone

#### Scenario: No room
- **WHEN** a version of a piece with no room builds
- **THEN** the build notice carries no size warning
