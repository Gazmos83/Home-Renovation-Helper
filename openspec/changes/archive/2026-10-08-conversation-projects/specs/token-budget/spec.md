## MODIFIED Requirements

### Requirement: Every call is counted and fitted before it is sent
Before every model call the request SHALL be counted — system text, tool schemas, the current turn, earlier history, and each image at a fixed cost — with a safety factor, against the model's context budget minus its output cap. When the earlier history does not fit, the exchanges that must be dropped (oldest first, never splitting a tool call from its result) SHALL be replaced by the active build's summary of them: a short "decisions so far" note about that build written by the Foreman slot's model from those exchanges, kept with the thread and that build, and refreshed only when the exchanges to drop reach past what it covers. A conversation with no active build SHALL use its own summary the same way. Switching the active build SHALL bring back that build's stored summary. The summary SHALL be sent inside the untrusted-content delimiters, labelled as a summary of earlier conversation, and SHALL NOT be the source of any figure: dimensions and prices come from the spec and the house file. Making or refreshing a summary SHALL be one model call counted and metered against the Foreman slot's budget like any other; when it is refused or fails, or the summary itself does not fit, the call SHALL fall back to the note that history was shortened. The stored conversation SHALL be unchanged in every case. When the system text, tools and current turn alone do not fit, the call SHALL be refused as too large with how many tokens were needed and available.

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
