# dev-panel Specification

## Purpose

Defines the developer panel's routes: model routing per slot, generation profiles and token restrictions per model, plugin enablement and invocations, and usage per day — all behind the developer gate.

## Requirements

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

### Requirement: Feedback is readable per slot, model and tier
The developer SHALL be able to read the render-feedback summary (up and down counts and latest comment time, grouped by slot, model and tier), and the comments of one group newest first, behind the developer gate. Renders started outside an agent turn SHALL be grouped under no slot and no model. Reading feedback SHALL NOT change routing.

#### Scenario: Ungrouped HTTP renders
- **WHEN** a still started through the renders route is rated up
- **THEN** the summary counts it in a row with no slot and no model at its tier

### Requirement: Render offload is managed from the developer panel
Behind the developer gate, the developer SHALL be able to:
- read whether offload is configured (host, port, user, remote Blender path and device shown; key file and known-hosts contents never shown);
- test the connection, reporting reachability, the remote Blender version and the GPU devices it lists;
- run the remote benchmark through the render guard;
- set the final target to `local` or `remote`;
- set an hourly rate in euros;
- read the last twenty remote jobs with estimate, actual, transfer seconds, outcome and the euro estimate from the hourly rate.

Setting the target to `remote` SHALL be refused while offload is not configured. A change SHALL apply to the next render without a restart.

#### Scenario: Remote target without configuration
- **WHEN** offload is not configured and the developer sets the final target to `remote`
- **THEN** the change is refused saying offload is not configured, and the target stays `local`

#### Scenario: Connection test
- **WHEN** the developer tests a reachable server running Blender 5.2.1 with one GPU
- **THEN** the response reports reachable, version 5.2.1 and the GPU's device name

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
