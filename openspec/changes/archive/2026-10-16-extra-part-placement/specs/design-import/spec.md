## MODIFIED Requirements

### Requirement: The import template guides another chat
The service SHALL ship an import template in the wrapper form whose `build` is the `custom-build` starter and whose `guide` states, for whoever fills it in:
- the shape and limits of material slots, modules, fronts, the envelope, extra parts, hardware lines, assembly notes and part overrides;
- that a module may list `side_folds` (at most one fold per left or right side: `from_mm`, `along` height or depth, `angle_deg` 1 to 89, `towards` inside or outside), and that overlay fronts, adjustable shelves and dividers on a folded module follow the folded opening;
- that a module may list `divider_spans` (one per divider, left to right: `from_board` "bottom" or a shelf number counting every shelf from the lowest, `to_board` "top" or a shelf number; only a fixed shelf can anchor a divider), and that without it every divider runs full height;
- that a module may list `shelf_kinds` ("fixed" or "adjustable" per shelf, lowest first, agreeing with `shelves` and `adjustable_shelves`), and that without it the fixed shelves are the lowest;
- that an extra part may list `placements`, one per piece (exactly `qty`), each with `x`, `y`, `z` (the piece's reference corner in mm in the build's frame), `length_along` and `width_along` (each `x`, `y` or `z`, never the same; the thickness takes the remaining axis), and optionally `roll_deg` and `tilt` (`towards`, `angle_deg`) for a piece set at an angle, with one worked example of a diagonal brace;
- that an extra part may list `end_cuts` (`across` width or thickness, `start_deg`, `end_deg`; the stated length is the longest edge);
- that modules, wall shelves and placed extra parts are drawn assembled, and an extra part without `placements` is laid flat beside the build;
- that a document is returned as JSON alone, with no other text;
- that a room survey is not part of the document.

The template SHALL be valid as shipped, and the owner SHALL be able to download it through an owner-gated route.

#### Scenario: Template valid as shipped
- **WHEN** the shipped import template is validated and derived
- **THEN** it is valid and derives the starter's cut-list rows and hardware lines

#### Scenario: Template downloaded
- **WHEN** the owner downloads the import template
- **THEN** the file is served as JSON with a download file name and holds the guide and the build

#### Scenario: Without a login
- **WHEN** the template route is called without the owner's session
- **THEN** it answers 401

#### Scenario: Guide names side folds
- **WHEN** the owner downloads the import template
- **THEN** its guide names `side_folds`, `from_mm`, `along`, `angle_deg` and `towards`

#### Scenario: Guide allows fronts on a fold
- **WHEN** the owner downloads the import template
- **THEN** its guide says overlay fronts, adjustable shelves and dividers follow the folded opening, and no longer says a folded module cannot carry dividers

#### Scenario: Guide names divider spans
- **WHEN** the owner downloads the import template
- **THEN** its guide names `divider_spans`, `from_board`, `to_board` and `shelf_kinds`, and says only a fixed shelf can anchor a divider

#### Scenario: Guide names extra-part placements
- **WHEN** the owner downloads the import template
- **THEN** its guide names `placements`, `length_along`, `width_along`, `roll_deg`, `tilt` and `end_cuts`, says unplaced extra parts are laid beside the build, and no longer says only modules are drawn assembled
