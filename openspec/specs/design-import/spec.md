# design-import Specification

## Purpose
Defines how a furniture design written outside the app, typically by another AI chat, enters it and leaves it again: the import document and its two forms, the shipped template with its guide, importing an attached design file as a new piece after the owner's confirmation, and exporting a version as a design document and as a shop bundle.

## Requirements

### Requirement: An import document is a design in one of two forms
The service SHALL accept as an import document either a bare custom-build document, or a wrapper of kind `package_import`, schema version 1, units `mm`, holding a `build` that is exactly a custom-build document and optionally a `guide` of at most 40 notes of at most 500 characters each. The `build`, or the bare document, SHALL be validated and derived by the same rules as a design written in the conversation. A field the schema does not define SHALL be refused by name, and the refusal SHALL be recorded as a generator-extension request. The service SHALL read nothing from the `guide`. A `survey` section SHALL be refused by name, with a reason saying that rooms are not imported and that Intake records a room. The document SHALL contain no code, expression, path or command, and nothing in it SHALL be executed.

#### Scenario: Bare design accepted
- **WHEN** the owner imports the shipped `custom-build` template file as it is
- **THEN** it previews as a valid design

#### Scenario: Wrapper with a guide accepted
- **WHEN** the owner imports the shipped import template unchanged
- **THEN** it previews as a valid design and nothing is read from its guide

#### Scenario: Survey refused
- **WHEN** an import document carries a `survey` section
- **THEN** it is refused naming `survey` and saying that Intake records rooms, and nothing is created

#### Scenario: Invented field refused by name
- **WHEN** a design written by another chat carries `modules[0].bevel_mm`
- **THEN** it is refused naming `modules[0].bevel_mm`, the field is recorded as a generator-extension request, and nothing is created

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

### Requirement: An attached design becomes a new piece after confirmation
When a turn carries a design file, the Designer SHALL be able to import it by its upload id. The file SHALL be read by the service, never retyped by the model, and only a design file of the same conversation SHALL be read.

A valid document SHALL be previewed (name, overall size in mm, module count, cut-list rows, hardware lines and any design-rule warnings) and SHALL pause for the owner's `yes`, with a package id the Designer proposes under the existing id rules. On `yes`:
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

### Requirement: A version exports as a design and as a bundle
The owner SHALL be able to download, through owner-gated routes, for any version of a piece:
- **its design:** an import document in the wrapper form, without a `guide`, whose `build` is the version's stored design. Importing it in a new conversation SHALL record an identical design.
- **its bundle:** a zip holding that design file, `cutlist.csv`, `hardware.csv`, `model.glb`, `screenshot.png` and, when the version has a still, `still.png`, and nothing else.

The bundle SHALL be refused with a 409 and a stated reason when the version's build has not succeeded. An unknown package or version SHALL answer 404. Neither download SHALL carry a model name, prompt, token count, cost or file-system path.

#### Scenario: Design round-trip
- **WHEN** the owner downloads the design of `hall-bench/v3` and imports it in a new conversation as `hall-bench-copy`
- **THEN** `hall-bench-copy/v1`'s stored design equals `hall-bench/v3`'s

#### Scenario: Bundle of a built version
- **WHEN** the owner downloads the bundle of a built version with a still
- **THEN** the zip holds exactly the design file, `cutlist.csv`, `hardware.csv`, `model.glb`, `screenshot.png` and `still.png`

#### Scenario: Bundle before the build
- **WHEN** the owner asks for the bundle of a version whose build is `running`
- **THEN** it answers 409 saying the version must be built first

### Requirement: An attached design becomes a piece's next version after confirmation
`import_design_version` SHALL take a design file's upload id and an existing piece's package id. The file SHALL be read by the service from the same conversation's upload and checked exactly as `import_design` checks it.

A valid document SHALL be previewed: name, overall size in mm, module count, cut-list rows, hardware lines and any design-rule warnings, together with the version it follows (the piece's latest). The preview pauses for `yes`. On `yes`:
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

### Requirement: A design file that matches an existing piece is named when it is attached
When the owner's message carries a design file and the conversation has no piece, the application SHALL check the file against the house file's pieces before any specialist runs. The file matches a piece when any of these holds:
- its file name, without `.json`, is the piece's id;
- the name inside the design, made into an id the way an apartment name is, is the piece's id;
- the name inside the design equals the piece's name, ignoring case.

On a match the application SHALL answer that turn itself, with no specialist and no room question. The answer names the file and the piece (name and id) and gives three ways on:
- to update the piece, attach the file in that piece's conversation, which imports it as the next version; when the piece has no conversation, name the piece in this conversation and attach the file again;
- to start over, delete the piece on the Pieces page and attach the file again;
- to keep both, reply "keep both" with a new name for the design, and the file is imported as a new piece under that name.

The answer SHALL be decided and written by the application, not by a model. A conversation already bound to the matching piece SHALL import the file as before. A file that matches no piece SHALL be handled as before.

When the owner's next message after that answer asks to keep both, the application SHALL hand the earlier design file to the Designer, together with the name the owner gave if any. The application decides this, not a model. The Designer imports the file as a new piece with `import_design`, under the new name. `import_design` SHALL take an optional name, which replaces the name inside the design before it is checked. The new name SHALL NOT equal any existing piece's name, ignoring case. When the owner gave no name, the Designer asks for one before calling the tool. The import is previewed and confirmed as any import.

#### Scenario: File named like an existing piece
- **WHEN** the owner attaches `kommode-harmony.json` in a new conversation and piece `kommode-harmony` exists
- **THEN** the reply names `kommode-harmony.json` and "Kommode Harmony (Höffner 13207807)" (`kommode-harmony`) with the three ways on
- **AND** no specialist runs, the room question is not asked, and nothing is imported

#### Scenario: Name inside the design matches
- **WHEN** the owner attaches `export.json` whose design is named "Sideboard" and piece `sideboard-1200` is named "Sideboard"
- **THEN** the reply names `sideboard-1200` with the three ways on

#### Scenario: Keep both with a new name
- **WHEN** after that reply the owner answers "keep both, call it Sideboard Hall"
- **THEN** the Designer previews importing `export.json` as a new piece named "Sideboard Hall"
- **AND** on yes the piece is created and `sideboard-1200` is unchanged

#### Scenario: Keep both without a name
- **WHEN** after that reply the owner answers "keep both"
- **THEN** the Designer asks for the new piece's name, and nothing is imported yet

#### Scenario: New name still matches
- **WHEN** `import_design` is called with the name "sideboard" while piece `sideboard-1200` is named "Sideboard"
- **THEN** the tool refuses saying a piece already has that name

#### Scenario: No match
- **WHEN** the owner attaches `lamellen-kommode.json` named "Lamellen-Kommode" and no piece has that id or name
- **THEN** the turn is handled as before

#### Scenario: Bound to the matching piece
- **WHEN** the owner attaches `kommode-harmony.json` in `kommode-harmony`'s own conversation
- **THEN** no conflict reply is given, and the file can be imported as `kommode-harmony`'s next version as before
