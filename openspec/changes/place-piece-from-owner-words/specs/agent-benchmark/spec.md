## Purpose

Live replays of core owner sentences through the real routed models, so a change of model, prompt or routing that breaks a core flow is caught before the owner meets it.

## ADDED Requirements

### Requirement: Core flows are replayed against the real models on request
The backend test suite SHALL hold benchmark cases marked `benchmark`. They SHALL be skipped unless pytest is run with `--benchmark` and an OpenRouter key is configured. Each case SHALL seed its own house-file state in the test database, send one owner sentence through the real Foreman graph with the models routed for each slot, and assert on observable outcomes only: the pause shown (question set, confirmation and its subject), the state stored, the tools called, and words that must not appear in the reply. A case SHALL NOT start a render: the render guard stays in force, and a case that reaches a render call fails. A case SHALL NOT assert on exact model wording. The token restrictions of the routed slots SHALL apply as in the app.

#### Scenario: Benchmarks skipped by default
- **WHEN** `uv run pytest -m "not slow"` runs without `--benchmark`
- **THEN** every `benchmark` case is skipped and no OpenRouter call is made

#### Scenario: Placement stated in the owner's words
- **WHEN** the case seeds `Wohnen` (five walls) as the conversation's room, a built and approved sideboard as the bound piece with no placement, runs with `--benchmark`, and sends "Please place the sideboard along wall 2 0 mm from wall 3."
- **THEN** no placement question set is shown, the placement is stored as wall 2 at 0 mm from its left end, the turn pauses on a `compose_room` confirmation, `render_turntable` is not called, and the reply does not contain "render"

#### Scenario: Benchmark failure names the step
- **WHEN** a benchmark case fails
- **THEN** the failure message names the step that failed (routing, question set, stored placement, pause or wording), with the specialist that answered and the tools it called
