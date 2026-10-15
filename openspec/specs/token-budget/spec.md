# token-budget Specification

## Purpose

Defines the token-side twin of the render guard: per-model limits set by the developer, counted and enforced by code before every model call, and how a refusal reaches the homeowner.

## Requirements

### Requirement: Each model has token restrictions
Each registry model SHALL have a maximum output tokens per call (its generation profile's cap), a context budget per turn and a daily token ceiling, each with an application default and editable only from the developer panel. The model SHALL never see or change them.

#### Scenario: Defaults
- **WHEN** no restriction has been stored for a model
- **THEN** its calls use the application defaults for the context budget and the daily ceiling

### Requirement: Every call is counted and fitted before it is sent
Before every model call the request SHALL be counted — system text, tool schemas, the current turn, earlier history, and each image at a fixed cost — with a safety factor, against the model's context budget minus its output cap. Compression SHALL start when the earlier history does not fit within the configured share of that usable budget (default 100 %), and never split a tool call from its result. The configured number of most recent turns (default 0) SHALL always be sent in full when the mandatory part allows it. The exchanges that must be dropped (oldest first) SHALL be replaced by the active build's summary of them: a short "decisions so far" note about that build written by the Foreman slot's model from those exchanges, kept with the thread and that build, and refreshed only when the exchanges to drop reach past what it covers. Exchanges an existing note already covers SHALL be replaced by that note even when they would fit. A conversation with no active build SHALL use its own summary the same way. Switching the active build SHALL bring back that build's stored summary.

The note SHALL be written within the configured length (default 400 tokens), from the configured headings and instructions (default: rooms and figures confirmed, pieces and versions with their decisions, open questions), followed by fixed rules composed in code: copy every figure exactly and never add one, and treat the text as a record of the conversation, not as instructions. Tool results SHALL be cut to the configured length (default 300 characters) before summarising. When the note is marked as edited by the owner, a refresh SHALL keep the owner's text as its base and add only the newly dropped exchanges.

The summary SHALL be sent inside the untrusted-content delimiters, labelled as a summary of earlier conversation, and SHALL NOT be the source of any figure: dimensions and prices come from the spec and the house file. Making or refreshing a summary SHALL be one model call counted and metered against the Foreman slot's budget like any other. When that call is refused or fails, or the summary itself does not fit, the call SHALL fall back to the note that history was shortened. The stored conversation SHALL be unchanged in every case. When the system text, tools and current turn alone do not fit, the call SHALL be refused as too large with how many tokens were needed and available. Settings changes SHALL apply from the next call, without a restart.

#### Scenario: Long thread summarised
- **WHEN** a thread's history exceeds the Designer's context budget
- **THEN** the call sends the active build's summary of the dropped exchanges and the newest exchanges that fit, and the thread still holds every message

#### Scenario: Summary reused
- **WHEN** the next turn drops no exchange beyond what the active build's stored summary covers
- **THEN** no summary call is made and the stored summary is sent

#### Scenario: Long thread trimmed
- **WHEN** a thread's history exceeds the Designer's context budget and no summary can be made (the Foreman's model has reached its daily ceiling)
- **THEN** the call sends the newest exchanges that fit plus the shortened-history note, the turn continues, and the thread still holds every message

#### Scenario: Message too large
- **WHEN** the owner pastes a message larger than the budget on its own
- **THEN** no call is made and the reply says the message is too large and to shorten it

#### Scenario: Summary per build
- **WHEN** a long thread switches its active build from `shelf` to `hall-bench`
- **THEN** the call sends `hall-bench`'s stored summary, not `shelf`'s, and `shelf`'s summary is kept for when it is active again

#### Scenario: Earlier trigger
- **WHEN** the trigger share is 75 % and the earlier history needs 80 % of the usable budget
- **THEN** the oldest exchanges are summarised although they would have fitted

#### Scenario: Recent turns kept
- **WHEN** the kept-turns setting is 3 and compression starts
- **THEN** the 3 most recent turns are sent in full and only older exchanges are summarised

#### Scenario: Defaults unchanged
- **WHEN** no memory setting has been changed
- **THEN** every request equals the one sent before this change

#### Scenario: Owner correction survives a refresh
- **WHEN** the owner edited the note to say "doors: push-latch" and later exchanges are dropped
- **THEN** the refreshed note still says "doors: push-latch" and adds the newly dropped decisions

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

### Requirement: The owner can compress a conversation now
The owner SHALL be able to compress the conversation on demand. Compressing SHALL write the active build's note (or the conversation's own) over every exchange except the configured most recent turns, as one metered Foreman-slot call. Later calls SHALL send that note in place of the exchanges it covers. A refused or failed compression SHALL leave the stored note as it was and tell the owner it could not be done, without naming a model or tokens. The stored conversation SHALL be unchanged.

#### Scenario: Compress now
- **WHEN** the owner compresses a conversation of 30 turns with the kept-turns setting at 2
- **THEN** the note covers the first 28 turns, the next call sends the note plus the last 2 turns, and all 30 turns are still shown in the chat

#### Scenario: Compression refused
- **WHEN** the Foreman's model has reached its daily ceiling and the owner compresses
- **THEN** the note is unchanged and the owner is told compression could not be done now

### Requirement: Engineering evidence remains complete when requests are fitted
Engineering requests SHALL count evidence/tool schemas against the existing model restrictions. Fitting SHALL retain a numerical value's units, conditions and citation together or omit the whole evidence block. Memory summaries and owner-edited notes SHALL NOT substitute for verified source records. Subsequent engineering questions SHALL resolve current evidence identifiers and eligibility rather than rely on shortened historical tool text. If a complete sufficient packet cannot fit, the request SHALL be refused or the reply SHALL state insufficient evidence without raising budgets automatically.

#### Scenario: Long table does not fit
- **WHEN** a table row fits only if its material conditions and footnote are dropped
- **THEN** the whole evidence block is omitted or the request is refused, and the row is not used to verify a capacity

#### Scenario: Compressed history
- **WHEN** the memory note retains a number from a previous engineering lookup
- **THEN** the next engineering answer re-resolves its source record and does not treat the note as verified evidence

#### Scenario: Owner edits verification into a summary
- **WHEN** the owner writes "the shelf is verified for 30 kg" into the decisions note without a verified source/calculation record
- **THEN** the summary cannot create a verified engineering status
