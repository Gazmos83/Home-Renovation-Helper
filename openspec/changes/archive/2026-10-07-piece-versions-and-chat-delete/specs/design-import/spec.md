## MODIFIED Requirements

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

## ADDED Requirements

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
