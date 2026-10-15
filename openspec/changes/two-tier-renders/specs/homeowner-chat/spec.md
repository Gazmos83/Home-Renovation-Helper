## MODIFIED Requirements

### Requirement: A render started in a thread posts a notice when it ends
When a render that a specialist's tool started in a thread ends, the service SHALL post one notice to that thread. This covers stills and turntables at every tier, of a piece version (alone or placed in a room), of an apartment shell, of a composition, and of a detail pass. The notice is written by code, not by a model.

- A finished render's notice SHALL name the tier, the kind and what was rendered, and say it is ready, for example "The draft turntable of hall-bench version 1 is ready." For a piece version it SHALL add that the result can also be checked in the Project panel.
- A failed render's notice SHALL say in plain words that it did not finish and that nothing new was published, for example "The draft turntable of hall-bench version 1 did not finish, so nothing new was published. You can ask for it again." It SHALL NOT carry the error text.
- A render started from a Studio page rather than a conversation SHALL post no notice. A render whose thread was deleted before it ended SHALL post nothing and SHALL still finish as it would have.
- Posting a notice SHALL NOT change the render's outcome; a failure to post SHALL be logged and the render's outcome kept.
- A notice SHALL NOT be sent to any model as part of the conversation, and SHALL obey the no-internals rule.

#### Scenario: Draft finished
- **WHEN** the Builder starts a draft turntable of `hall-bench` version 1 from a conversation and it finishes
- **THEN** the thread holds a notice with outcome `succeeded`, package `hall-bench`, version 1, saying the draft turntable is ready and can also be checked in the Project panel

#### Scenario: Final finished
- **WHEN** the owner approves a final still of `hall-bench` version 3 and it finishes
- **THEN** the thread holds a notice with outcome `succeeded`, package `hall-bench` and version 3, naming the final still

#### Scenario: Render failed
- **WHEN** a draft turntable of `hall-bench` version 2 started from a conversation fails
- **THEN** the thread holds a notice with outcome `failed` saying it did not finish, and the notice contains no error text, host path or model slug

#### Scenario: Started from the Studio
- **WHEN** a draft still is started from the Studio's render route
- **THEN** no thread gets a notice

#### Scenario: Thread deleted meanwhile
- **WHEN** the conversation is deleted while its render runs
- **THEN** the render finishes and publishes as usual and no notice is written

#### Scenario: Not sent to the model
- **WHEN** the owner sends a message after a notice was posted
- **THEN** the specialist's model call contains no message with the notice's text
