## ADDED Requirements

### Requirement: A door can carry slats
A door entry SHALL accept an optional `slats`, with these fields:
- `count`: the number of slats on each slatted leaf, 1 to 40.
- `width`: each slat's face width in mm.
- `material`: a material slot. The slot's thickness is the slats' thickness, which is how far they stand proud of the door.
- `orientation`: `vertical` or `horizontal`. Optional; the default is `vertical`.
- `margin_mm`: the distance from every edge of the leaf to the slats. Optional; the default is 0.
- `leaves`: the leaves of the entry that carry slats, numbered from 1 on the left. Optional; the default is every leaf.

On each slatted leaf the slats follow the leaf:
- vertical slats run the leaf's height less twice the margin, and are spread across its width less twice the margin;
- horizontal slats run the leaf's width less twice the margin, and are spread across its height less twice the margin;
- the outermost slats lie on the margins, and the gaps between neighbouring slats are equal;
- a single slat is centred on the leaf.

A change to the door's size, `count`, `width`, `orientation` or `margin_mm` re-spaces the slats with no other edit. An unknown slats field SHALL be refused by name, as any unknown field is. `slats` on a drawer or flap entry is an unknown field.

Slats SHALL be refused, naming the entry's `slats` and with nothing built, when:
- the gap between neighbouring slats would be under 3 mm; the refusal gives the leaf's size across the slats and the largest count that fits;
- the margin leaves no length or width for the slats;
- `leaves` names a leaf outside the entry's count, or names one leaf twice;
- `material` is not a defined material slot;
- the module has `side_folds`, which this change does not support.

Slats SHALL be cut parts. Each door row that carries slats SHALL have one further cut-list row, `<door row id>-slat`, named "Door slat", with:
- quantity: `count` times the number of slatted leaves in that row;
- length: the slat's length; width: `width`; thickness: the slot's thickness;
- material: the slot's material, with grain along the length (vertical, or left-right for horizontal slats);
- a note giving the count per door, the orientation, the gap in mm and "glued to the door face".

The row SHALL be priced like any cut-list row. The door row's own size SHALL be unchanged.

A built version SHALL draw each slat as one object, in front of its leaf at its place. Objects are named by the slat row id, with `#<n>` for further pieces, counted leaf by leaf from the left, then left to right for vertical slats or top to bottom for horizontal ones. Each SHALL be listed in the `fronts` layer and parented to its module's empty, so it moves with its module in the exploded view.

Slats SHALL NOT change `overall` and SHALL NOT count in the envelope check, as fronts and handles do not. They add no hardware line and nothing to the drilling list. A door without `slats` SHALL be drawn, derived and listed exactly as before.

#### Scenario: Vertical slats on the right door only
- **WHEN** module `kommode`, 800 mm wide, has one entry of two hinged doors (leaves 397 × 747 mm) with `slats` count 8, width 30, material slot `slats` of 12 mm and `leaves` [2]
- **THEN** the cut list holds `kommode-door-1-slat` ×8 at 747 × 30 × 12 mm with a note giving 8 vertical per door and a 22.4 mm gap, and the build draws `kommode-door-1-slat` and `#2` … `#8` in the `fronts` layer, all in front of the right door: the first flush with that door's left edge and the last flush with its right edge

#### Scenario: Horizontal slats
- **WHEN** the same entry's slats are count 10, width 40, `orientation` horizontal and `leaves` [2]
- **THEN** the cut list holds `kommode-door-1-slat` ×10 at 397 × 40 × 12 mm with grain left-right, and the ten slats run across the right door from its top edge to its bottom edge with equal gaps

#### Scenario: Slats on both doors by default
- **WHEN** the entry carries vertical `slats` count 6 and width 40 with no `leaves`
- **THEN** the cut list holds `kommode-door-1-slat` ×12, and each of the two doors has six slats

#### Scenario: Fewer slats re-spaces them
- **WHEN** a revision changes that entry's slat `count` from 8 to 5
- **THEN** the next version's slat row is ×5 and the five slats are evenly spaced across the right door with no other field changed

#### Scenario: Turning the slats
- **WHEN** a revision changes that entry's slat `orientation` from vertical to horizontal
- **THEN** the next version's slats run across the door's width and are spaced over its height, and the slat row's length is the leaf's width

#### Scenario: Slats follow a resized door
- **WHEN** a revision widens module `kommode` from 800 to 900 mm while the slats are vertical
- **THEN** the right door is wider, its slats are evenly spaced across the new width, and the slat row's length and quantity are unchanged

#### Scenario: Margin
- **WHEN** vertical slats carry `margin_mm` 20 on a 397 × 747 mm leaf
- **THEN** each slat is 707 mm long and the outer slats are 20 mm in from the leaf's left and right edges

#### Scenario: Too many slats refused
- **WHEN** a 397 mm wide leaf carries vertical `slats` count 13 and width 30
- **THEN** the spec is refused naming that entry's `slats`, giving the leaf's width and saying at most 12 such slats fit, and nothing is built

#### Scenario: Leaf outside the count refused
- **WHEN** an entry of two doors carries slats with `leaves` [3]
- **THEN** the spec is refused naming that entry's `slats.leaves` and saying the entry has 2 doors

#### Scenario: Slats on a drawer refused
- **WHEN** a drawer entry carries `slats`
- **THEN** the spec is refused naming `slats` as an unknown field

#### Scenario: Slats on a folded module refused
- **WHEN** a module with a left side fold has a door entry with slats
- **THEN** the spec is refused naming that entry's `slats` and saying slats on a folded module are not supported

#### Scenario: Doors without slats unchanged
- **WHEN** a version without any `slats` is rebuilt
- **THEN** its cut list, hardware and exported objects equal the previous build's

#### Scenario: Overall size unchanged
- **WHEN** a version with slats is built
- **THEN** `overall` equals that of the same version without slats, and `hardware.csv` and the drilling list are unchanged by them

### Requirement: A handle on slats is drawn on the slats and warned about
A door entry SHALL accept both `slats` and a `handle`, with either orientation. On a slatted leaf the handle SHALL be placed as on a plain leaf, but SHALL stand proud of the slats' face rather than the door's face. On a leaf without slats it is drawn as before.

Every leaf with both slats and a handle SHALL carry a slat-handle warning: "the handle on door <n> of `<door row id>` is mounted over the slats, so its screws pass through a slat into the door and its posts may land on a slat or in a gap; check the screw length and the handle's position before drilling". The warning SHALL appear:
- in the cut list: the slat row's note ends with "Warning:" and the warning, so `cutlist.csv` and the inspector's cut-list table show it;
- in the conversation, written by the application rather than the model:
  - in every confirmation that would create a version carrying it (creating a piece, revising one, importing a design or a version), beside the design-rule warnings;
  - in the Designer's summary of the active build, so the Designer can mention it.

A version where no leaf has both SHALL show no slat-handle warning.

#### Scenario: Handle on horizontal slats
- **WHEN** the right door of `kommode` carries horizontal 12 mm slats and the entry has a vertical 300 mm bar handle on the meeting edges
- **THEN** the right door's handle stands 30 mm proud of the slats' face, the left door's handle stands 30 mm proud of the door face, and both are at the same height

#### Scenario: Warning in the cut list
- **WHEN** that version is built
- **THEN** the note of `kommode-door-1-slat` in `cutlist.csv` and in the inspector's cut-list table ends with a warning naming door 2 of `kommode-door-1` and saying to check the screw length and the handle's position before drilling

#### Scenario: Warning in the revision confirmation
- **WHEN** the owner asks for a knob on both doors while the right door has slats, and the Designer proposes the revision
- **THEN** the confirmation shows the slat-handle warning for door 2 before the owner answers, and no warning for door 1

#### Scenario: Warning in an import preview
- **WHEN** an attached design has slats and a handle on the same door
- **THEN** the import preview shows the slat-handle warning beside any design-rule warnings

#### Scenario: No handle, no warning
- **WHEN** a version has slats but no handle on any slatted leaf
- **THEN** no slat row note, confirmation or summary carries a slat-handle warning
