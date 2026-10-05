## Purpose

Defines the token-side twin of the render guard: per-model limits set by the developer, counted and enforced by code before every model call, and how a refusal reaches the homeowner.

## ADDED Requirements

### Requirement: Each model has token restrictions
Each registry model SHALL have a maximum output tokens per call (its generation profile's cap), a context budget per turn and a daily token ceiling, each with an application default and editable only from the developer panel. The model SHALL never see or change them.

#### Scenario: Defaults
- **WHEN** no restriction has been stored for a model
- **THEN** its calls use the application defaults for the context budget and the daily ceiling

### Requirement: Every call is counted and fitted before it is sent
Before every model call the request SHALL be counted — system text, tool schemas, the current turn, earlier history, and each image at a fixed cost — with a safety factor, against the model's context budget minus its output cap. Earlier exchanges SHALL be dropped oldest first, never splitting a tool call from its result, with a note that history was shortened; the stored conversation SHALL be unchanged. When the system text, tools and current turn alone do not fit, the call SHALL be refused as too large with how many tokens were needed and available.

#### Scenario: Long thread trimmed
- **WHEN** a thread's history exceeds the Designer's context budget
- **THEN** the call sends the newest exchanges that fit plus the shortened-history note, and the thread still holds every message

#### Scenario: Message too large
- **WHEN** the owner pastes a message larger than the budget on its own
- **THEN** no call is made and the reply says the message is too large and to shorten it

### Requirement: The daily ceiling refuses before spending
Before every call the tokens already recorded for that model since the start of the day (in the configured time zone), plus this call's counted input and its output cap, SHALL be compared with the model's daily ceiling; a call that would pass it SHALL NOT be made. Usage rows with no token figures SHALL count as their counted estimate.

#### Scenario: Ceiling reached
- **WHEN** the Designer's model has used its ceiling today and the owner asks for a revision
- **THEN** no model call is made and the reply says the Designer has reached today's limit and when it resets

### Requirement: A budget refusal reaches the homeowner by role, not model
A refusal by the budget SHALL end the turn with a reply naming the specialist by role and the reason in plain words, with nothing pending and nothing stored half-way; the response SHALL NOT contain a model name, a token count or a cost.

#### Scenario: Refusal wording
- **WHEN** the Researcher's call is refused by the daily ceiling
- **THEN** the reply names the Researcher, says the limit resets at midnight, and contains no model slug or token figure
