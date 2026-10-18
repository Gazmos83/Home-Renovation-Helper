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
- that a door, drawer or flap entry may carry a `handle` (`kind` bar or knob, `length` for a bar, `orientation`, `edge` meeting, left or right for doors, `inset_mm`, `at_mm`, `finish`, optional `key`), that a push-latch door takes no handle, that one `handle` serves every leaf of its entry, and that a handle given this way is drawn and listed, so it is not also written as a hardware line;
- that a module may list `hanging_rails` (`bay`, `z` the rail centre above the bottom panel, optional `inset_y_mm`, `finish`, `key`, `support_key`), and that the rail and its supports are drawn and listed, so they are not also written as hardware lines;
- that hinges, shelf pins, drawer runners, flap stays, push latches, confirmat screws and brackets are counted by the app's rules and are not written as hardware lines, that knobs and pulls are written as a front's `handle`, and that every hardware line needs a whole-number `qty`;
- that hardware lines the app's rules already count are removed on import, and the preview lists each removal;
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

#### Scenario: Guide names handles
- **WHEN** the owner downloads the import template
- **THEN** its guide names `handle`, `kind`, `orientation`, `edge`, `inset_mm`, `at_mm` and `finish`, says a push-latch door takes no handle, and says a modelled handle is not also written as a hardware line

#### Scenario: Guide names rule-counted hardware
- **WHEN** the owner downloads the import template
- **THEN** its guide names `hanging_rails`, says hinges, shelf pins and runners are counted by the app, says knobs and pulls are a `handle`, and says `qty` is required

## ADDED Requirements

### Requirement: An import corrects its hardware against the rules
`import_design` and `import_design_version` SHALL check every hand-written hardware line of a valid document against the hardware the rules in force derive for it. The rules in force are the version's data sheets, the design rules and the built-in fallbacks. The check is made in code, never by a model, before the preview. Each line is handled as follows:
- **Same id as a rule-counted line:** removed. The rule's count stands.
- **Item text matches a catalog entry of a rule-counted kind:** a match is a catalog entry's `matches` phrase, compared as a lower-cased substring. The line is removed when the design derives a line of that kind. Otherwise it is kept, with a warning that nothing in the design uses it.
- **Reads as a knob, pull or handle while no front carries a `handle`:** kept, with a warning that it is not drawn and can be written as a front's `handle`.
- **Anything else:** kept as written.

The preview SHALL list every removal and warning under "Hardware corrections". A removal names the line's id, item and quantity, and the rule-counted line that replaces it with its count. On `yes`, the corrected document SHALL be stored as the version's design. On `no`, nothing is created. A line's `qty` SHALL stay required: a line without a whole-number `qty` refuses the import naming the field, as today.

#### Scenario: Duplicate hinges removed
- **WHEN** an imported design with eight hinged doors also lists `cabinet-hinges` "110 degree soft-close concealed cabinet hinges" ×8
- **THEN** the preview lists the removal of `cabinet-hinges` ×8 in favour of `hinge-concealed-110` with its rule count, and the stored design has no `cabinet-hinges` line

#### Scenario: Same id not added twice
- **WHEN** an imported design lists `hinge-concealed-110` ×8 by hand and its doors derive 24
- **THEN** the hand-written line is removed and the version lists `hinge-concealed-110` ×24, not ×32

#### Scenario: Knob line warned, not converted
- **WHEN** an imported design lists `cabinet-knobs` "Antique brass cabinet knobs" ×2 on a module whose fronts carry no handle
- **THEN** the line is kept, and the preview warns that it is not drawn and can be written as a `handle` with kind `knob` and finish `brass`

#### Scenario: Unknown item kept
- **WHEN** an imported design lists `murphy-mechanism` ×1
- **THEN** the line is kept as written, and the version marks it as not shown in the model

#### Scenario: Missing quantity still refused
- **WHEN** a hardware line has no `qty`
- **THEN** the import is refused naming `qty`, and nothing is created
