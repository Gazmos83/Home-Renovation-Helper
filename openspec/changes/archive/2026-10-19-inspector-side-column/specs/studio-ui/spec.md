## ADDED Requirements

### Requirement: The inspector's stage controls sit in a grouped column beside the 3D view
Wherever a piece version or a room composition version is shown in 3D (the piece inspector page, the Measured Rooms page, a conversation's split view and the Workspace's piece and room panes), every clickable control of the 3D stage SHALL sit in one column to the right of the 3D view, and the 3D view SHALL take the remaining width. The column SHALL stay to the right at every width, including the split view and the Workspace panes. When its contents are taller than the 3D view, the column SHALL scroll on its own and the 3D view SHALL keep its height.

The column SHALL be divided into sections, each with a heading the owner clicks to fold or unfold it. Within a section the buttons SHALL be listed one above the other, one per line, as thin as their text allows, and all as wide as the column; the column SHALL be as wide as its longest button label (owner, 2026-10-19). Every section SHALL be open when the view is first shown. Folding a section SHALL NOT change the state of any switch in it.

For a room composition the sections SHALL be, in this order:
1. **Views**: Iso, Front, Side, Plan, Workshop and Blueprint.
2. **Room**: All walls, one switch per wall, the floor, the ceiling and, when the version has dimensions, `dimensions`.
3. **Furniture**: All items and one switch per built item, or the single items switch when the build report does not list each item's meshes. A version with no items SHALL show no Furniture section.

For a piece version the sections SHALL be, in this order:
1. **Views**: Iso, Front, Side, Plan, Workshop, Blueprint and Exploded, and the explode slider while Exploded is chosen.
2. **Parts**: one switch per layer the version's `spec.json` names, and `dimensions`.

The switches SHALL keep their names, their starting state and their effect on the model as before; only their place changes. The tabs, the version switcher, the verdict, the overall dimensions line, the straight-on views and the turntable link SHALL stay outside the column.

#### Scenario: Room controls grouped
- **WHEN** the owner opens the 3D view of a room composition version with four walls and two built items
- **THEN** a column right of the view shows a Views section with Iso, Front, Side, Plan, Workshop and Blueprint, a Room section with All walls, wall 1 to wall 4, floor, ceiling and dimensions, and a Furniture section with All items and the two items, all open, and the ceiling is off

#### Scenario: Piece controls grouped
- **WHEN** the owner opens `/pieces/murphy-bed/versions/1`
- **THEN** a column right of the view shows a Views section with Iso, Front, Side, Plan, Workshop, Blueprint and Exploded, and a Parts section with carcass, backs, shelves, fronts, extras and dimensions, all open

#### Scenario: Explode slider in Views
- **WHEN** the owner chooses Exploded
- **THEN** the explode slider appears in the Views section, and it is gone again when the owner chooses Workshop

#### Scenario: Folding keeps switches
- **WHEN** the owner switches wall 2 off, folds the Room section and unfolds it again
- **THEN** wall 2 is still off and its meshes stay hidden while the section is folded

#### Scenario: Split view keeps the column right
- **WHEN** the owner opens a piece version in a conversation's split view
- **THEN** the column is to the right of the 3D view, not below it

#### Scenario: Room without items
- **WHEN** the owner opens the 3D view of a room composition version that places no items
- **THEN** the column shows the Views and Room sections and no Furniture section
