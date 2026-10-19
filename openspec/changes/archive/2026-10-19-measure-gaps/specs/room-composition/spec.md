## ADDED Requirements

### Requirement: An item's gaps in a composition version are measured by code
For one item of a room composition version, the application SHALL compute clear distances from that version's stored document only, so they never change after the version is made. Every distance SHALL be in whole millimetres. A distance SHALL be 0 when the shapes touch or overlap.
- **To each wall** of the item's room: the shortest plan distance between the item's footprint and the wall, with the wall labelled `wall <n>` as in the surface map.
- **To each other item** in the same room, except hidden items and LED strips: the shortest plan distance between the two footprints. When the footprints overlap in plan because one hangs above the other, the distance SHALL be the vertical clearance between them, and the answer SHALL say so.
- **To the ceiling:** the room height minus the item's top. For a hung item, the answer SHALL also give the height of its underside above the floor.

An item SHALL be named by its id or by its name or package id. A name that matches more than one item SHALL be refused, listing the matching ids. An unknown item, an unknown version, or a document without a room plan SHALL answer that it cannot be measured, with the reason. An apartment-scope composition SHALL be refused with a plain sentence for now.

#### Scenario: Bed against wall 2 of Wohnen
- **WHEN** Wohnen v12 has a 1000 mm wide, 300 mm deep bed on wall 2 (3000 mm long, between walls 1 and 3), 700 mm from the end at wall 3, and a 2500 mm ceiling with the bed 700 mm tall
- **THEN** the gaps are 700 mm to wall 3, 1300 mm to wall 1, 0 mm to wall 2, and 1800 mm to the ceiling

#### Scenario: Shelf hung above a desk
- **WHEN** a shelf hangs with its underside at 1500 mm directly above a 750 mm tall desk
- **THEN** the gap between them is given as 750 mm of vertical clearance

#### Scenario: Ambiguous name
- **WHEN** two items in the version are both named "Chair" and the item is given as "Chair"
- **THEN** nothing is measured and the answer lists both item ids
