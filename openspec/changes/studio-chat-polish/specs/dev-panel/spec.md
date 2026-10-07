## ADDED Requirements

### Requirement: A conversation's model calls are readable by the developer
The developer SHALL be able to read, for one conversation, every model call recorded for it — time, slot, model slug, input and output tokens (or the counted estimate, marked as such, when the gateway reported none) — newest first, including title and summary calls. Each usage row SHALL record the conversation it was made for. Usage rows SHALL survive the conversation's deletion, without the link to it. The route SHALL sit behind the developer gate.

#### Scenario: One turn's calls
- **WHEN** a turn routes Foreman → Intake and Intake's call is the thread's first turn, followed by the title call
- **THEN** the conversation's calls list three rows — `foreman`, `intake`, `foreman` — each with its model slug and token figures

#### Scenario: Unknown conversation
- **WHEN** the developer reads the calls of a thread id that does not exist
- **THEN** the response is 404

#### Scenario: Panel disabled
- **WHEN** the panel is disabled and the route is called with a valid session
- **THEN** the response is 404
