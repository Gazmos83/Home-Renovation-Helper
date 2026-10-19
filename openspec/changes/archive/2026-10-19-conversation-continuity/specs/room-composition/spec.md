## ADDED Requirements

### Requirement: A wall-hung piece holds its height above the floor
A `piece` item placed against a wall MAY carry `mount_height_mm` in its placement: the height of the piece's underside above the floor, a whole number of millimetres from 0. Without it the piece stands on the floor, as before. A free placement or a `stand-in` or `model` item carrying `mount_height_mm` SHALL be refused naming the item and the field. A piece whose `mount_height_mm` plus its overall height passes the room's ceiling SHALL be refused naming the item, its top and the ceiling.

A hung piece SHALL fill the height from `mount_height_mm` up to `mount_height_mm` plus its overall height. It SHALL clash with another item whose footprint it overlaps only where their height ranges overlap; a standing item fills the height from the floor to its height, and a piece whose underside is exactly at the top of the item below it is accepted. It SHALL take the door and window checks only when its underside is below the top of the opening (sill plus opening height). The placement rules SHALL apply to it as to any standing item. The built room SHALL show the piece at that height.

The same optional field SHALL be accepted by the placement the owner saves for a piece version in a room, and by the room fit check, with the same ceiling refusal.

#### Scenario: Sideboard hung above a kommode
- **WHEN** Wohnen has a 2500 mm ceiling, lamellen-kommode (914 mm tall) stands on wall 1 at offset 0, and sideboard-1200 version 2 (800 mm tall, 1350 mm wide) is placed on wall 1 at offset 0 with `mount_height_mm` 1700
- **THEN** the document is accepted and the built room shows the sideboard from 1700 to 2500 mm above the floor

#### Scenario: Hung piece clashes with a tall item
- **WHEN** a piece hung at 1200 mm overlaps the footprint of a 1500 mm tall stand-in
- **THEN** the document is refused naming both ids

#### Scenario: Hung piece above the ceiling
- **WHEN** an 800 mm tall piece is given `mount_height_mm` 1800 in a room with a 2500 mm ceiling
- **THEN** it is refused naming the item, its 2600 mm top and the 2500 mm ceiling

#### Scenario: Hung piece clears a door
- **WHEN** a piece hung at 2100 mm is placed on a wall across a door 2000 mm high
- **THEN** the door check does not refuse it

#### Scenario: Height on a stand-in refused
- **WHEN** a stand-in's placement carries `mount_height_mm`
- **THEN** the document is refused naming the item and `mount_height_mm`
