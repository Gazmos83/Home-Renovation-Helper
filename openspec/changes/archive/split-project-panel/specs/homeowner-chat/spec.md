## MODIFIED Requirements

### Requirement: A render started in a thread posts a notice when it ends
When a render that a specialist's tool started in a thread ends, the service SHALL post one notice to that thread. This covers stills and turntables at every tier, of a piece version (alone or placed in a room), of an apartment shell, of a composition, and of a detail pass. The notice is written by code, not by a model.

- A finished render's notice SHALL name the tier, the kind and what was rendered, and say it is ready, for example "The draft turntable of hall-bench version 1 is ready." For a piece version it SHALL add that the result can also be checked in the Piece panel.
- A failed render's notice SHALL say in plain words that it did not finish and that nothing new was published, for example "The draft turntable of hall-bench version 1 did not finish, so nothing new was published. You can ask for it again." It SHALL NOT carry the error text.
- A render started from a Studio page rather than a conversation SHALL post no notice. A render whose thread was deleted before it ended SHALL post nothing and SHALL still finish as it would have.
- Posting a notice SHALL NOT change the render's outcome; a failure to post SHALL be logged and the render's outcome kept.
- A notice SHALL NOT be sent to any model as part of the conversation, and SHALL obey the no-internals rule.

#### Scenario: Draft finished
- **WHEN** the Builder starts a draft turntable of `hall-bench` version 1 from a conversation and it finishes
- **THEN** the thread holds a notice with outcome `succeeded`, package `hall-bench`, version 1, saying the draft turntable is ready and can also be checked in the Piece panel

#### Scenario: Final finished
- **WHEN** the owner approves a final still of `hall-bench` version 3 and it finishes
- **THEN** the thread holds a notice with outcome `succeeded`, package `hall-bench` and version 3, naming the final still

#### Scenario: Render failed
- **WHEN** a preview turntable of `hall-bench` version 2 started from a conversation fails
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

## ADDED Requirements

### Requirement: The owner can read and edit a conversation's brief
The service SHALL let the owner read a conversation's brief (room, purpose, highest the piece may be in mm, style, budget in EUR) and save an edited one, outside a chat turn. A save SHALL validate the brief (purpose non-empty, height above 0, budget 0 or more, room one of the stored rooms), store it as the conversation's brief and as the bound piece's brief when there is one, and keep style and budget as preferences only while the memory settings save preferences. A hand-edited height limit SHALL clear the note naming the version that raised it. A save while a turn is running, or with an invalid brief, SHALL be refused with a reason and change nothing. The thread SHALL come from the path and the owner from the cookie. The read and the save SHALL NOT carry a model name, prompt, token count or cost.

#### Scenario: Save
- **WHEN** the owner saves a brief with budget 900 on a conversation bound to `hall-bench`
- **THEN** the conversation's brief and `hall-bench`'s stored brief both hold budget 900

#### Scenario: Refused
- **WHEN** the owner saves a brief with an empty purpose
- **THEN** the save is refused, saying the purpose is required, and the stored briefs are unchanged

#### Scenario: Turn running
- **WHEN** the owner saves a brief while a turn is running in that conversation
- **THEN** the save is refused and nothing changes

### Requirement: The agents' facts carry the brief's settings
The facts every conversation turn gives the Foreman and the specialists SHALL include the brief's settings that are set (room, purpose, highest the piece may be in mm, style, budget in EUR) as one line, taken from the conversation's brief, else from the bound piece's stored brief, so a brief edited outside a chat turn is read on the next turn. A setting that is not set SHALL be left out; with no brief the line SHALL be absent.

#### Scenario: Edited brief is read
- **WHEN** the owner saves a brief with budget 900 and then sends a message
- **THEN** the Foreman's routing prompt and the specialist's prompt both contain "budget: 900 EUR"

#### Scenario: No brief
- **WHEN** a conversation has no brief
- **THEN** the facts carry no brief line
