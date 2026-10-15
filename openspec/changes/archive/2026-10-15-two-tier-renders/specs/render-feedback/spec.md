## MODIFIED Requirements

### Requirement: Every render run records its origin
When a guarded render starts, the service SHALL record a render run with the package, version, render (still, turntable, room still, room turntable, detail still, detail turntable, or a restyle variant of a piece named by its variant id), tier and start time. When an agent turn requested the render, the run SHALL also record the thread, the turn's trace id, the owner's message that led to it, and the slot and model that called the render tool. Origin records SHALL NOT be written into the version folder, and SHALL NOT appear in any homeowner response. A failure to record an origin SHALL be logged and SHALL NOT stop the render. A restyle variant of a composition SHALL NOT be recorded as a render run.

#### Scenario: Builder starts a draft turntable
- **WHEN** the Builder starts a `draft` turntable after the owner wrote "show me it from all sides"
- **THEN** a render run records tier `draft`, the thread, the trace id, that message, slot `builder` and the Builder's routed model

#### Scenario: Render started over HTTP
- **WHEN** a `draft` still is started through the renders route
- **THEN** a render run is recorded with the package, version, render and tier, and no thread, prompt or model

#### Scenario: Restyle variants recorded
- **WHEN** the Builder starts a `draft` restyle of `hall-bench` v2 with the looks `walnut` and `sage-green`
- **THEN** two render runs are recorded, one per variant, each naming its variant id, tier `draft`, the thread and slot `builder`

#### Scenario: Composition restyle not recorded
- **WHEN** a `draft` restyle of the composition `Wohnen` v2 runs
- **THEN** no render run is recorded for its variants

### Requirement: The owner rates a render up or down with an optional comment
The owner SHALL be able to give the latest succeeded run of a version's render, including a published restyle variant of a piece, a rating of up or down, with an optional comment of at most 1 000 characters. Rating again SHALL replace the run's rating, and clearing SHALL remove it. A rating for a render with no succeeded run SHALL be refused, saying the render does not exist yet. A rating SHALL carry the run it was given for, so a later re-render starts unrated. The rating routes SHALL require the owner's session.

#### Scenario: Thumbs down with a comment
- **WHEN** the owner rates the `draft` turntable of `hall-bench` v2 down with "too dark"
- **THEN** the rating is stored against that turntable's latest run with the comment

#### Scenario: Changed mind
- **WHEN** the owner rates the same turntable up afterwards
- **THEN** that run has one rating, up, and the earlier one is gone

#### Scenario: Re-rendered
- **WHEN** a rated `draft` turntable is rendered again at tier `draft`
- **THEN** the new run has no rating, and the earlier rating stays with the earlier run

#### Scenario: Nothing rendered
- **WHEN** the owner rates the still of a version that has no still
- **THEN** it is refused saying the render does not exist yet

#### Scenario: Variant rated
- **WHEN** the owner rates the `walnut` variant of `hall-bench` v2 up with "love this"
- **THEN** the rating is stored against that variant's run with the comment

#### Scenario: Unknown variant
- **WHEN** the owner rates a variant id that the version does not hold
- **THEN** it is refused saying the render does not exist yet

## ADDED Requirements

### Requirement: A variant's rating reaches the agents as appearance only
When a rated restyle variant is among the piece's recent ratings in the Designer's or Lighting & materials' context, it SHALL be listed with its version, variant id, tier, rating and comment, and SHALL be marked "appearance only, not a priced material". The owner SHALL be able to rate a variant in chat as for any render: the Builder proposes the rating naming the variant, and nothing is stored before `yes`. When the owner does not say which render, the proposal SHALL default to the bound piece's most recent render, a variant included. A rating whose variant was later replaced SHALL stay in the history.

#### Scenario: Look preference reaches the Designer
- **WHEN** the `walnut` variant of `hall-bench` v2 was rated up with "love this"
- **THEN** the Designer's context lists v2, the variant `walnut`, `draft`, up, that comment and "appearance only, not a priced material"

#### Scenario: Variant rated in chat
- **WHEN** right after a restyle the owner writes "the walnut one is great 👍"
- **THEN** the reply asks to record "up — the walnut one is great" on the `walnut` variant, and it is stored only after `yes`

#### Scenario: Replaced variant keeps its rating
- **WHEN** a rated variant is replaced by a thirteenth variant
- **THEN** its rating still appears among the recent ratings, and it no longer appears among the version's renders
