## ADDED Requirements

### Requirement: An LED strip is a wall-mounted composition item
A composition document MAY hold items of type `led-strip`. An `led-strip` item SHALL have a unique id, a `name`, and:
- `length_mm`: a whole number from 100 to 10 000;
- `lumens_per_m`: a whole number from 50 to 3000;
- `kelvin`: a whole number from 1800 to 6500;
- `mount_height_mm`: a whole number from 0 to the room's ceiling height minus 10, the height of the strip above the floor;
- `facing`: `"down"`, `"up"` or `"out"`. It is optional and defaults to `"down"`.

It SHALL be placed against a wall (wall index and offset in millimetres). A free-standing placement SHALL be refused naming the item. In an apartment scope it SHALL also name its room. It SHALL NOT carry `layer`, `light`, `colour`, `width_mm`, `depth_mm` or `height_mm`; each is refused as an unknown field.

An LED strip SHALL be refused, naming its id and the problem, when it:
- runs past the end of its wall;
- reaches the ceiling;
- crosses a door or a window on its wall at a height within that opening (from its sill to its top);
- overlaps another LED strip on the same wall, both along the wall and in height.

An LED strip SHALL be exempt from the footprint overlap check with every other item type, and placement rules SHALL NOT be applied to it. Each strip SHALL count as one light towards the composition's light limit, and it SHALL make its room count as lit for the dimming of the room's general lights.

#### Scenario: Strip under the kitchen wall cabinets
- **WHEN** `Küche` has a 3200 mm wall 2, and an `led-strip` `under-cabinets` of 2400 mm at 500 lumens per metre and 3000 K is placed on wall 2 at offset 400 with `mount_height_mm: 1450`
- **THEN** it is accepted with facing `down`, even though a kitchen piece stands against wall 2 at the same offset

#### Scenario: Strip past the wall end
- **WHEN** a 2400 mm strip is placed on a 2000 mm wall at offset 0
- **THEN** it is refused naming the strip as running past the end of its wall

#### Scenario: Strip across a window
- **WHEN** a strip at 1200 mm runs across a window on its wall whose sill is at 900 mm and whose top is at 2100 mm
- **THEN** it is refused naming the strip, the window and its wall

#### Scenario: Strip below a window
- **WHEN** a strip at 300 mm runs along a wall below a window whose sill is at 900 mm
- **THEN** it is accepted

#### Scenario: Two strips overlap
- **WHEN** two strips on wall 1 at the same height overlap along the wall
- **THEN** the document is refused naming both ids

#### Scenario: Free-standing strip
- **WHEN** an `led-strip` has a placement with `x_mm`, `y_mm` and `rotation_deg`
- **THEN** it is refused naming the item

#### Scenario: Size field on a strip
- **WHEN** an `led-strip` carries `height_mm`
- **THEN** it is refused naming `height_mm` as an unknown field

### Requirement: An LED strip is built and reported
The headless build of a composition, and every render, restyle variant and detail-pass copy rebuilt from it, SHALL build each LED strip as a thin emissive bar, 10 mm thick and 15 mm deep, along its wall at its height, glowing in its kelvin colour. It SHALL also add one rectangular area light of the strip's length, pointing down, up or into the room as its facing says. The light's power SHALL be the strip's length in metres times its lumens per metre times the configured watts per lumen. The light SHALL be named after its item. The surface map SHALL count the strip's meshes under the items.

The build report SHALL list, for each strip, its length, lumens per metre, kelvin, power in watts, wall, offset, height and facing.

#### Scenario: Built strip
- **WHEN** `Küche` is built with the strip `under-cabinets` (2400 mm, 500 lm per metre, 3000 K, facing down) and the configured factor is 0.05 W per lumen
- **THEN** the scene holds an emissive bar 2400 mm long at 1450 mm on wall 2 and a 60 W area light of 2400 mm named after `under-cabinets` pointing down, `Küche`'s general lights are dimmed, and the build report lists the strip with its values

#### Scenario: Draft render with a strip
- **WHEN** a `draft` still of a composition version with a strip is rendered through the guard
- **THEN** it is rendered on Eevee with the strip lit, and the guard's tier, estimate and approval rules apply unchanged
