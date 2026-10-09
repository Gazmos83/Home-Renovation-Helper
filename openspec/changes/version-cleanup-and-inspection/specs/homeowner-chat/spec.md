## ADDED Requirements

### Requirement: A build started in a thread posts a notice when it ends
When a build of a piece version that a specialist's tool started in a thread ends, the service SHALL post one build notice to that thread. This covers builds started by creating a piece, by a revision, by a rebuild, and by the Builder's build tool. The notice SHALL be written by code, not by a model, and SHALL carry the piece and version.
- A finished build's notice SHALL say that the version is built, for example "hall-bench version 2 is built."
- A failed build's notice SHALL say in plain words that the version did not build, for example "hall-bench version 2 did not build. You can ask for it again." It SHALL NOT carry the error text.

A build started from a Studio route SHALL post no notice. A build whose thread was deleted before it ended SHALL post nothing and SHALL still finish. Posting SHALL NOT change the build's outcome; a failure to post SHALL be logged. A build notice, like a render notice, SHALL NOT be sent to any model and SHALL obey the no-internals rule. Render notices SHALL be unchanged.

#### Scenario: Revision built
- **WHEN** the owner confirms a revision of `hall-bench` in a conversation and version 2 builds
- **THEN** the thread holds a build notice with outcome `succeeded`, package `hall-bench` and version 2, saying it is built

#### Scenario: Build failed
- **WHEN** version 2 of `hall-bench`, started from a conversation, fails to build
- **THEN** the thread holds a build notice with outcome `failed` saying it did not build, with no error text, host path or model slug

#### Scenario: Started from the Studio
- **WHEN** the owner submits an edited spec to the package route
- **THEN** no thread gets a build notice

#### Scenario: Not sent to the model
- **WHEN** the owner sends a message after a build notice was posted
- **THEN** the specialist's model call contains no message with the notice's text
