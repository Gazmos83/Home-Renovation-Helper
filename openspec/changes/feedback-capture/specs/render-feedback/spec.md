## Purpose

Defines how the owner's reaction to a render is captured: what each render run records about where it came from, how a thumbs up or down and a comment are given from the Pieces page or in chat, how ratings reach tracing as scores and tags, and how the developer reads them per model and tier.

## ADDED Requirements

### Requirement: Every render run records its origin
When a guarded render starts, the service SHALL record a render run with the package, version, render (still, turntable, room still, room turntable, detail still or detail turntable), tier and start time. When an agent turn requested the render, the run SHALL also record the thread, the turn's trace id, the owner's message that led to it, and the slot and model that called the render tool. Origin records SHALL NOT be written into the version folder, and SHALL NOT appear in any homeowner response. A failure to record an origin SHALL be logged and SHALL NOT stop the render.

#### Scenario: Builder starts a draft turntable
- **WHEN** the Builder starts a `draft` turntable after the owner wrote "show me it from all sides"
- **THEN** a render run records tier `draft`, the thread, the trace id, that message, slot `builder` and the Builder's routed model

#### Scenario: Render started over HTTP
- **WHEN** a `draft` still is started through the renders route
- **THEN** a render run is recorded with the package, version, render and tier, and no thread, prompt or model

### Requirement: The owner rates a render up or down with an optional comment
The owner SHALL be able to give the latest succeeded run of a version's render a rating of up or down, with an optional comment of at most 1 000 characters. Rating again SHALL replace the run's rating, and clearing SHALL remove it. A rating for a render with no succeeded run SHALL be refused, saying the render does not exist yet. A rating SHALL carry the run it was given for, so a later re-render starts unrated. The rating routes SHALL require the owner's session.

#### Scenario: Thumbs down with a comment
- **WHEN** the owner rates the `draft` turntable of `hall-bench` v2 down with "too dark"
- **THEN** the rating is stored against that turntable's latest run with the comment

#### Scenario: Changed mind
- **WHEN** the owner rates the same turntable up afterwards
- **THEN** that run has one rating, up, and the earlier one is gone

#### Scenario: Re-rendered
- **WHEN** a rated turntable is rendered again at tier `preview`
- **THEN** the new run has no rating, and the earlier rating stays with the earlier run

#### Scenario: Nothing rendered
- **WHEN** the owner rates the still of a version that has no still
- **THEN** it is refused saying the render does not exist yet

### Requirement: Feedback given in chat is confirmed before it is recorded
When the owner reacts to a render in words, the Builder or Lighting & materials SHALL propose a rating, naming the render, version and tier with the rating and comment it read. Nothing SHALL be stored before the owner answers `yes`. On any other answer nothing SHALL be stored. The proposal SHALL default to the bound piece's most recent render when the owner does not say which.

#### Scenario: Spoken thumbs down
- **WHEN** after a draft turntable the owner writes "that's far too dark 👎"
- **THEN** the reply asks to record "down — far too dark" on that turntable, and it is stored only after `yes`

#### Scenario: Declined
- **WHEN** the owner answers `no` to a proposed rating
- **THEN** nothing is stored

### Requirement: Ratings reach tracing as scores and tags
When tracing is configured, every stored or changed rating SHALL be recorded as a score on the trace of the turn that started the render, when there is one. The score SHALL carry the rating and comment. The rating SHALL also be recorded as a feedback trace tagged with the rating, the tier, and the slot and model of the run when known. A tracing failure SHALL be logged and SHALL NOT affect the stored rating. With tracing off, nothing SHALL be sent anywhere.

#### Scenario: Scored on the render's turn
- **WHEN** the owner rates up a turntable the Builder started in a traced turn
- **THEN** that turn's trace carries a positive render-feedback score, and a feedback trace is tagged with `up`, the tier and the Builder's model

#### Scenario: Tracing unreachable
- **WHEN** tracing is configured but unreachable and the owner rates a render
- **THEN** the rating is stored and the owner sees no error

### Requirement: The developer reads feedback per model and tier
The developer panel SHALL list rating counts grouped by slot, model and tier: up count, down count, and the time of the latest comment. It SHALL be able to list the comments of one group, newest first. Feedback SHALL NOT change routing or any setting by itself.

#### Scenario: Summary after three ratings
- **WHEN** two Builder-started `draft` turntables were rated up and one down
- **THEN** the Builder's model at tier `draft` shows 2 up and 1 down
