## ADDED Requirements

### Requirement: A door's leaves can have their own materials
A door entry SHALL accept an optional `leaf_materials`. It maps a door number of the entry (1 to `count`, numbered from the left as in `slats.leaves`) to a material slot. A door it names is cut in that slot's material; a door it does not name keeps the carcass material, as every door does today. An unknown field inside it is refused by name, as any unknown field is, and `leaf_materials` on a drawer or flap entry is an unknown field.

`leaf_materials` SHALL be refused, naming the entry's `leaf_materials` and with nothing built, when:
- it names a door outside the entry's count; the refusal says how many doors the entry has;
- a slot is not a defined material slot;
- a slot's thickness differs from the carcass slot's thickness; the refusal gives both thicknesses;
- the module has `side_folds`, which this change does not support.

When the doors of one entry are cut in more than one material, the entry's door row SHALL split into one row per door, numbered from the left: `<entry row id>-1`, `<entry row id>-2` and so on, each with quantity 1, that door's material and its own hinge line. This is the naming doors of different shapes already use. An entry whose doors all share one material, including every entry without `leaf_materials`, SHALL keep its one row exactly as before.

Everything that refers to a split door's row SHALL use that door's own row id:
- the slat row of a slatted door is `<door row id>-slat`, with that door's slats only;
- its handle and its drilling-list entries;
- the slat-handle warning.

A `part_overrides` entry naming the former shared row SHALL be refused by name, as any override of a row that does not exist is.

A built version SHALL draw each door under its own row id, as an object of its row, in the colour of its row's material. Placement, size, hinge side, slats and handles SHALL be as without `leaf_materials`. `overall` and the envelope check SHALL be unchanged.

#### Scenario: Black right door, oak left door, side by side
- **WHEN** module `kommode`, 800 mm wide with an `oak` carcass slot of 18 mm, has one entry of two hinged doors with `leaf_materials` {"2": "black_paint"} (an 18 mm slot whose material is black painted MDF)
- **THEN** the cut list holds `kommode-door-1-1` ×1 in oak and `kommode-door-1-2` ×1 in black painted MDF, both 747 × 397 × 18 mm, the hinge lines total the same as for the unsplit pair, and the build draws the two doors side by side at their usual places, the right one black

#### Scenario: Slats on the black door
- **WHEN** that entry also carries `slats` count 8, width 30, material `slats` and `leaves` [2]
- **THEN** the cut list holds `kommode-door-1-2-slat` ×8, and the build draws the eight slats in front of the black door only

#### Scenario: Same material everywhere keeps one row
- **WHEN** `leaf_materials` names both doors with the carcass slot, or is left out
- **THEN** the cut list holds `kommode-door-1` ×2 as before, and the built objects are unchanged

#### Scenario: Door outside the count refused
- **WHEN** an entry of two doors carries `leaf_materials` {"3": "black_paint"}
- **THEN** the spec is refused naming that entry's `leaf_materials` and saying the entry has 2 doors

#### Scenario: Unknown slot refused
- **WHEN** `leaf_materials` names a slot `walnut` that `materials` does not define
- **THEN** the spec is refused naming that entry's `leaf_materials` and `walnut` as an undefined material slot

#### Scenario: Thickness mismatch refused
- **WHEN** `leaf_materials` names a 12 mm slot while the carcass slot is 18 mm
- **THEN** the spec is refused naming that entry's `leaf_materials`, giving 12 mm and 18 mm

#### Scenario: Override of the former pair row refused
- **WHEN** a split entry's spec keeps a `part_overrides` entry for `kommode-door-1`
- **THEN** the spec is refused naming that override and saying no derived cut-list row is named `kommode-door-1`
