## Purpose

Defines the developer panel's routes: model routing per slot, generation profiles and token restrictions per model, plugin enablement and invocations, and usage per day — all behind the developer gate.

## ADDED Requirements

### Requirement: Routing is changed per slot to a probed model
The developer SHALL be able to read each slot's routed model and the registry, and route a slot to another available registry model; the change SHALL be refused naming the model unless the gateway probe passes for it (with an image for an image slot), SHALL be stored as that slot's override, SHALL apply to the next turn without a restart, and SHALL never set a fallback. Resetting a slot SHALL restore the file's routing.

#### Scenario: Route the Designer
- **WHEN** the developer routes the Designer to `anthropic/claude-haiku-4.5` and its probe passes
- **THEN** the next Designer call uses it and the override is listed

#### Scenario: Probe fails
- **WHEN** the probe for the chosen model reports a guardrail block
- **THEN** the change is refused naming the model and the routing is unchanged

### Requirement: Generation profiles and token restrictions are edited per model
The developer SHALL be able to read, set and reset each model's temperature (where supported), output cap (bounded by the model and the application ceiling), context budget and daily ceiling; an out-of-range value SHALL be refused naming the field. Changes SHALL apply to the next call without a restart.

#### Scenario: Ceiling lowered
- **WHEN** the developer lowers a model's daily ceiling below today's usage
- **THEN** the next call for that model is refused by the budget

### Requirement: Plugins and usage are visible to the developer
The developer SHALL be able to list plugins with kind, role, tools, global state and default, enable or disable one globally, read an HTTPS plugin's recent invocations (outcome and duration only), and read token usage per model per day for a chosen number of days.

#### Scenario: Usage today
- **WHEN** the developer reads usage for one day after three Designer calls
- **THEN** the Designer's model shows today's input and output token totals

### Requirement: The panel is behind the developer gate
Every developer route SHALL answer 404 when the developer panel is disabled and 401 without the owner's session, exactly as the existing developer gate.

#### Scenario: Panel disabled
- **WHEN** the panel is disabled and a developer route is called with a valid session
- **THEN** the response is 404
