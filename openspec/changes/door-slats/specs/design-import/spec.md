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
- that a door entry may carry `slats` (`count` per door, `width`, `material` a slot whose thickness is how far they stand proud, optional `orientation` vertical or horizontal, `margin_mm` and `leaves`), that slats follow the door and are cut-list parts, so they are not also written as extra parts, and that a handle on slats is drawn on them with a warning to check its screws and position;
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

#### Scenario: Guide names slats
- **WHEN** the owner downloads the import template
- **THEN** its guide names `slats`, `count`, `width`, `orientation`, `margin_mm` and `leaves`, and says slats are not also written as extra parts

#### Scenario: Guide names handles
- **WHEN** the owner downloads the import template
- **THEN** its guide names `handle`, `kind`, `orientation`, `edge`, `inset_mm`, `at_mm` and `finish`, says a push-latch door takes no handle, and says a modelled handle is not also written as a hardware line

#### Scenario: Guide names rule-counted hardware
- **WHEN** the owner downloads the import template
- **THEN** its guide names `hanging_rails`, says hinges, shelf pins and runners are counted by the app, says knobs and pulls are a `handle`, and says `qty` is required

### Requirement: An attached design becomes a new piece after confirmation
When a turn carries a design file, the Designer SHALL be able to import it by its upload id. The file SHALL be read by the service, never retyped by the model, and only a design file of the same conversation SHALL be read.

A valid document SHALL be previewed (name, overall size in mm, module count, cut-list rows, hardware lines, any design-rule warnings and any slat-handle warnings) and SHALL pause for the owner's `yes`, with a package id the Designer proposes under the existing id rules. On `yes`:
- the piece and version 1 are recorded in the house file, with the change line `imported from <file name>`;
- the conversation is bound to the piece;
- the headless build starts.

On `no` nothing is created and the reason returns to the Designer.

The import SHALL be refused, with nothing created, in each of these cases:
- the conversation already has a piece; the refusal says the file can be imported as that piece's next version, or as a new piece in a new conversation;
- the package id is in use; the refusal says the file can be imported as that piece's next version;
- the design-rule outcome is a refusal;
- the document is invalid; the refusal names every problem the validation found.

The imported piece SHALL then be revised, approved, priced and placed exactly like a piece designed in the conversation.

#### Scenario: Imported and built
- **WHEN** the owner attaches `wall-unit.json` written by another chat, the preview shows the wall unit, and the owner answers `yes`
- **THEN** piece `wall-unit` version 1 exists in the house file with the change line `imported from wall-unit.json`, the conversation is bound to it, and its build is queued

#### Scenario: Slat-handle warning in the preview
- **WHEN** the attached design has slats and a knob handle on the same door
- **THEN** the preview shows the slat-handle warning for that door before the owner answers

#### Scenario: Declined
- **WHEN** the owner answers `no` to the import preview
- **THEN** no piece or folder is created and the conversation stays without a piece

#### Scenario: Conversation already has a piece
- **WHEN** the owner attaches a design in a conversation bound to `hall-bench`
- **THEN** the import is refused saying it can be imported as `hall-bench`'s next version or as a new piece in a new conversation, and `hall-bench` is unchanged

#### Scenario: Id in use
- **WHEN** the Designer imports a file as `murphy-bed` and `murphy-bed` exists
- **THEN** the import is refused saying it can be imported as `murphy-bed`'s next version, and nothing is created

#### Scenario: Another conversation's file
- **WHEN** the Designer names the upload id of a design attached in another conversation
- **THEN** the import is refused and nothing is read

#### Scenario: Imported piece can be approved
- **WHEN** the imported `wall-unit` version 1 has built and the owner approves it
- **THEN** the approval is recorded as for any piece

### Requirement: An attached design becomes a piece's next version after confirmation
`import_design_version` SHALL take a design file's upload id and an existing piece's package id. The file SHALL be read by the service from the same conversation's upload and checked exactly as `import_design` checks it.

A valid document SHALL be previewed: name, overall size in mm, module count, cut-list rows, hardware lines, any design-rule warnings and any slat-handle warnings, together with the version it follows (the piece's latest). The preview pauses for `yes`. On `yes`:
- the next version is recorded with the imported design and the change line `imported from <file name>, replacing version N`;
- the conversation is bound to the piece;
- the headless build starts.

Earlier versions SHALL be untouched. On `no` nothing is created and the reason returns to the Designer.

The import SHALL be refused, with nothing created, in each of these cases:
- the package id names no piece;
- the conversation is bound to a different piece;
- the file is another conversation's upload, or an image;
- the design-rule outcome is a refusal;
- the document is invalid; the refusal names every problem, inside the untrusted-content delimiters.

#### Scenario: Updated design for an existing piece
- **WHEN** the owner attaches `murphy-bed.json` in a new conversation, asks for it to become the Murphy bed's next version, and answers `yes`
- **THEN** `murphy-bed` version 2 exists with the file's design and the change line `imported from murphy-bed.json, replacing version 1`, the conversation is bound to `murphy-bed`, and its build is queued

#### Scenario: Bound to another piece
- **WHEN** the conversation is bound to `hall-bench` and the Designer imports a file as the next version of `murphy-bed`
- **THEN** the import is refused naming `hall-bench`, and neither piece changes

#### Scenario: Declined
- **WHEN** the owner answers `no` to the version-import preview
- **THEN** no version or folder is created
