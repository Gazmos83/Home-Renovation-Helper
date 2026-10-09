## MODIFIED Requirements

### Requirement: A composition is versioned and built headless
A confirmed composition SHALL be stored as a new version folder for its scope, holding the normalised document. That version SHALL be recorded as revised from the previous version, if any. Earlier versions SHALL never change. The build SHALL run in headless Blender under the one-process rule. It SHALL generate the room (or every room of the apartment) with its walls, openings, floor and ceiling. It SHALL place each piece from that version's built model, each stand-in as a box in its colour, and each model from the library, stretched to exactly its stated size on each axis and standing on the floor. A room composition with no items SHALL build the room alone. It SHALL publish `model.blend`, `model.glb`, a screenshot and a build report. The build report SHALL list each item's final size and, for each library model, its per-axis scale factors; for an empty room the report's item list is empty. The build report SHALL also hold a surface map. The surface map SHALL name every surface the owner can switch: each wall by its number (prefixed with its room's name for an apartment), the floor and the ceiling (per room for an apartment), and the items. For each surface it SHALL list the mesh names in `model.glb` that belong to it. A piece version that is not built SHALL fail the build naming that piece; it SHALL never be built implicitly.

#### Scenario: Build of a three-item room
- **WHEN** the owner confirms `Wohnen` with one approved piece, one stand-in and one model
- **THEN** a new version folder holds the document, `model.blend`, `model.glb`, a screenshot and a report naming the three items with their sizes, and the version's status reads `succeeded`

#### Scenario: Build of an empty room
- **WHEN** the owner confirms `Hall` with no items
- **THEN** a new version folder holds the document, `model.blend` and `model.glb` with the room's walls, openings, floor and ceiling and no item, a screenshot and a report with an empty item list, and the version's status reads `succeeded`

#### Scenario: Surface map
- **WHEN** `Hall` is a four-walled room and its composition build succeeds
- **THEN** the report's surface map names wall 1 to wall 4, the floor, the ceiling and the items, and every mesh in `model.glb` belongs to exactly one of them

#### Scenario: Piece not built
- **WHEN** a placed piece version has no successful build
- **THEN** the composition build fails naming that piece and version, and no `model.blend` or `model.glb` is published

#### Scenario: Model scaled
- **WHEN** a library model measured at 0.9 × 0.8 × 1.0 m is placed with a stated size of 800 × 700 × 900 mm
- **THEN** it is stretched to exactly 800 × 700 × 900 mm, its lowest point rests on the floor, and the build report states its per-axis scale factors
