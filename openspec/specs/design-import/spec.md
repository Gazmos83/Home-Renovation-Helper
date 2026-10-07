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
- that only modules are drawn assembled;
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

### Requirement: An attached design becomes a new piece after confirmation
When a turn carries a design file, the Designer SHALL be able to import it by its upload id. The file SHALL be read by the service, never retyped by the model, and only a design file of the same conversation SHALL be read.

A valid document SHALL be previewed (name, overall size in mm, module count, cut-list rows, hardware lines and any design-rule warnings) and SHALL pause for the owner's `yes`, with a package id the Designer proposes under the existing id rules. On `yes`:
- the piece and version 1 are recorded in the house file, with the change line `imported from <file name>`;
- the conversation is bound to the piece;
- the headless build starts.

On `no` nothing is created and the reason returns to the Designer.

The import SHALL be refused, with nothing created, in each of these cases:
- the conversation already has a piece; the refusal says to start a new conversation for the import;
- the package id is in use;
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
- **THEN** the import is refused saying to start a new conversation for it, and `hall-bench` is unchanged

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
