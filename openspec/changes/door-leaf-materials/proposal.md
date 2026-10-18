## Why

The owner's Höffner dresser has an oak left door and a black right door carrying oak slats, side by side. The schema cannot express this. All the leaves of a door entry are cut in the carcass material and grouped into one cut-list row (`kommode-door-1` ×2), and `part_overrides` can only target a whole row.

On 2026-10-17 the Designer worked around this in `lamellen-kommode` v3. It split the pair into two door entries to give the right door its own row, but entries stack top to bottom, so the doors turned 90°. The confirmation did not say the layout changed. The next revision was then refused, and the bot told the owner the design "can't be built".

This is a ladder step 2 request (generator extension): the schema and the generator must grow, through this change.

## What Changes

- A door entry accepts an optional `leaf_materials`. It maps a door number (1 to `count`, numbered from the left as in `slats.leaves`) to a material slot. Doors it does not name keep the carcass material.
- **Validation.** It is refused by name, with nothing built, when:
  - a door number is outside the entry's count;
  - a slot is undefined;
  - a slot's thickness differs from the carcass thickness;
  - the module has `side_folds` (as for slats).
- **Cut list.** When an entry's doors differ in material, the door row splits into one row per door: `<entry row>-1`, `<entry row>-2`, each qty 1 with its own material and hinge count. This is the naming leaves of different shapes already use. A pair with no `leaf_materials`, or with every door in the same material, stays one row as today.
- **Rows on a split door.** The slat row, handles and the drilling-list entries follow the split. A slatted door's slat row becomes `<door row>-slat` of the door it sits on.
- **Build.** The generator draws each door under its own row id, so it takes its slot's colour (for example a black paint slot is drawn black). The layout, `overall` and the envelope are unchanged.
- **Revising and confirming.**
  - `revise_package` can change one door's material by writing the entry's `leaf_materials`, with no other change to the fronts.
  - The confirmation and the Designer's piece summary name each door's material ("2 doors (hinge, door 2 black_paint, 8 vertical slats 30 mm on door 2)").
  - A revision that changes a module's front layout SHALL say so in its confirmation, written by code. A layout change is a different number of entries, or a changed door count or entry type, as in "kommode: front layout changes from 1 entry of 2 doors side by side to 2 entries stacked top to bottom". This makes a silent 90° turn visible.
- **Instructions.** The Designer instruction says that one door's own colour or material is `leaf_materials`, never a split of a pair into separate entries. The import template guide gains one line for it.

Ladder step 2. Agents touched: the Designer (instruction, revise confirmation, piece summary), the Builder only through the generator. The render guard and the bpy allow-list are not affected: no render tier changes and no live script is added.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `furniture-packages`: ADDED requirement "A door's leaves can have their own materials" (schema, refusals, cut-list split, build colour).
- `design-agents`: ADDED requirements "A revision names each door's material and says when the front layout changes" and "The Designer gives one door its own material without splitting the pair".
- `design-import`: ADDED requirement "The import template names per-door materials".

## Impact

- `backend/app/blender/schemas.py`: `DoorIn.leaf_materials` and its validators; a slot and thickness check in `_check_fronts`.
- `backend/app/blender/custom_build/derive.py`:
  - a leaf-material resolver;
  - `_group_leaves` keyed on material too;
  - `_add_front_rows` gives the material per row;
  - `slat_layout`, `handle_layout` and the drilling list use the split door row id.
- `backend/app/blender/generators/build_custom_build.py`: `_add_front_boxes` emits one piece per split row.
- `backend/app/agent/revise.py`: `describe_front` names door materials; a code-written front-layout line in the revise confirmation.
- `backend/app/agent/instructions/designer.md` and `backend/fixtures/packages/templates/import-template.json`: one line each.
- Tests for the spec, generator (fake and `--blender`), revise, piece note, instructions and template.
- No migration, no API change, no frontend change: the cut-list table already shows rows as derived.
