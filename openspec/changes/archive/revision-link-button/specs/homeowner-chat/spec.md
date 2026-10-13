## ADDED Requirements

### Requirement: A revision posts a notice with a link to its version
When a tool in a thread records a new version of a piece by revising it, rebuilding it or importing a design over it, the service SHALL post one `revision` notice to that thread as soon as the version is recorded, without waiting for its build. The notice SHALL be written by code, not by a model, and SHALL carry the piece and the new version, for example "hall-bench version 2 is created." It SHALL NOT carry error text, host paths or model slugs. The chat SHALL show it with an "Open version N" button, centered in the chat window, that opens that version in the inspector beside the chat. A revision notice SHALL NOT be sent to any model. Build and render notices SHALL be unchanged.

A version recorded from a Studio route SHALL post no revision notice. A failure to post SHALL be logged and SHALL NOT change the revision or its build.

#### Scenario: Revision confirmed
- **WHEN** the owner confirms a revision of `hall-bench` in a conversation and version 2 is recorded
- **THEN** the thread holds a `revision` notice for package `hall-bench` and version 2, posted before the build ends

#### Scenario: Button opens the version
- **WHEN** the owner presses "Open version 2" on that notice
- **THEN** the inspector opens beside the chat on `hall-bench` version 2

#### Scenario: Build fails
- **WHEN** version 2 fails to build
- **THEN** the revision notice and its button remain, and the build notice says the version did not build

#### Scenario: Started from the Studio
- **WHEN** the owner submits an edited spec to the package route
- **THEN** no thread gets a revision notice

#### Scenario: Not sent to the model
- **WHEN** the owner sends a message after a revision notice was posted
- **THEN** the specialist's model call contains no message with the notice's text
