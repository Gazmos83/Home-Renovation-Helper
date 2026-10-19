## ADDED Requirements

### Requirement: A piece's room render shows it at its saved height
A room-scene document's placement MAY carry `mount_height_mm`, with the same meaning and ceiling refusal as in a room composition. A room still or turntable SHALL import the version's model with its underside at that height above the floor, and `scene.json` SHALL record it with the placement. Without it the piece stands on the floor, as before. The render runs through the guard at its tier as any room render.

#### Scenario: Hung sideboard in a draft still
- **WHEN** a `draft` room still is requested for sideboard-1200 version 2 whose saved placement in Wohnen has `mount_height_mm` 1700
- **THEN** the still shows the sideboard's underside at 1700 mm and `room/scene.json` records `mount_height_mm` 1700 in the placement

#### Scenario: Placement without a height
- **WHEN** a room render's placement has no `mount_height_mm`
- **THEN** the piece stands on the floor as before
