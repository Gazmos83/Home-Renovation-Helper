## ADDED Requirements

### Requirement: A revision fits the build to a shelf that protrudes past the front
When a revision leaves any module with a board, including a shelf set by `shelf_depths_mm` with `shelf_depth_align` `"back"`, that reaches in front of the build's front plane (y = 0 in build millimetres), the revision SHALL be fitted before validation: every module's `y` and every wall shelf's `y` SHALL rise by the largest such overhang, and, when the build has an envelope, the envelope's depth SHALL rise by the same amount. No other field SHALL change and no document without a protruding board SHALL be altered. A build without an envelope SHALL have its module and wall-shelf positions moved the same way and no envelope added. The fitted document SHALL be validated as any revision; a document that is still refused (for example an overlap) SHALL be refused with that reason and nothing SHALL be saved. A revision that has already moved the build clear of y = 0 SHALL be fitted only for the remaining shortfall.

#### Scenario: One deeper shelf on a cabinet
- **WHEN** module `cabinet` (400 mm deep, 12 mm back, envelope depth 400 mm, `y` 0) is revised to `shelf_depths_mm` `[null, 550, null, null]` with `shelf_depth_align` `"back"`
- **THEN** the shelf's front is 162 mm before the module front, `cabinet`'s `y` becomes 162, the envelope depth becomes 562 mm, and the revision validates

#### Scenario: A row of modules moves together
- **WHEN** a build with modules `left` and `right` at `y` 0 gives `right` a shelf that protrudes 100 mm
- **THEN** both modules and any wall shelf move back 100 mm and the envelope grows 100 mm, so the modules' backs stay flush

#### Scenario: No protrusion, unchanged
- **WHEN** a revision gives no board a position in front of y = 0
- **THEN** no `y` and no envelope depth changes

#### Scenario: Other overflow is still refused
- **WHEN** a revision makes a module wider than the envelope
- **THEN** it is refused as before and the fit changes nothing

### Requirement: A folded module may carry a back-aligned shelf that protrudes past its front
On a module with `side_folds`, a shelf with `shelf_depth_align` `"back"` whose depth exceeds the folded inner depth SHALL be accepted: its rear stays on the carcass inner rear, the part in front of the carcass front lies outside the folds, and only the part inside the carcass SHALL be held to the folds, so the board's cut width is the narrowest inner width over that part. A shelf with `"front"` align deeper than the folded inner depth SHALL still be refused, naming `modules[n].shelf_depths_mm`. The module's bounds, overall depth, cut list and model SHALL include the protruding part, and a document without such a shelf SHALL derive and be drawn exactly as before.

#### Scenario: Protruding shelf on a folded cabinet
- **WHEN** a 400 mm deep cabinet with a left side fold from 1100 mm along height at 26° (inner depth 388 mm) is given `shelf_depths_mm` `[null, 550, null]` with `"back"` align
- **THEN** it is accepted, the shelf is cut 550 mm deep at the width the fold allows at its height, and the fold stays in the document

#### Scenario: Front-aligned shelf still refused
- **WHEN** the same cabinet is given a 550 mm shelf with `"front"` align
- **THEN** it is refused, naming `modules[0].shelf_depths_mm` and the folded inner depth of 388 mm
