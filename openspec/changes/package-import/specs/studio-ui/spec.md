## ADDED Requirements

### Requirement: Designs are imported and exported from the Studio
The conversation view SHALL let the owner attach a design file (`.json`) as well as images. An attached design SHALL be shown by its file name, not as a thumbnail. A refusal of the file SHALL be shown in plain words.

The Pieces page SHALL offer:
- a download of the import template, with one line saying to give it to another AI chat and attach the returned file in a conversation;
- for each version, a design download;
- for a built version, a bundle download.

Neither view SHALL show a model name, prompt, token count or cost. The import and export flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Design attached
- **WHEN** the owner picks `wall-unit.json` in a conversation
- **THEN** a chip named `wall-unit.json` is shown and is sent with the next message

#### Scenario: Downloads on the Pieces page
- **WHEN** the owner opens a piece whose version 2 is built and version 3 is building
- **THEN** version 2 offers the design and the bundle downloads, and version 3 offers only the design

#### Scenario: Template offered
- **WHEN** the owner opens the Pieces page
- **THEN** a link downloads the import template, with the line on how to use it
