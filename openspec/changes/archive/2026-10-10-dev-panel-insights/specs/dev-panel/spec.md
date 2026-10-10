## MODIFIED Requirements

### Requirement: A conversation's model calls are readable by the developer
The developer SHALL be able to read, for one conversation, every model call recorded for it — time, slot, model slug, input and output tokens (or the counted estimate, marked as such, when the gateway reported none), the estimated cost when the model has a stored price, and a link to the call's Langfuse trace when tracing is on and the call has a trace id — newest first, including title and summary calls. Each usage row SHALL record the conversation it was made for. Usage rows SHALL survive the conversation's deletion, without the link to it. The calls page SHALL say whether tracing is on. No Langfuse key SHALL be sent to the browser. The route SHALL sit behind the developer gate.

#### Scenario: One turn's calls
- **WHEN** a turn routes Foreman → Intake and Intake's call is the thread's first turn, followed by the title call
- **THEN** the conversation's calls list three rows — `foreman`, `intake`, `foreman` — each with its model slug and token figures

#### Scenario: Trace link shown
- **WHEN** tracing is on and a call row has a trace id
- **THEN** the row carries that trace's Langfuse URL, and the response holds no Langfuse key

#### Scenario: Tracing off
- **WHEN** tracing is off
- **THEN** the rows carry no trace link and the page says tracing is off

#### Scenario: Unknown conversation
- **WHEN** the developer reads the calls of a thread id that does not exist
- **THEN** the response is 404

#### Scenario: Panel disabled
- **WHEN** the panel is disabled and the route is called with a valid session
- **THEN** the response is 404

## ADDED Requirements

### Requirement: Call totals are shown as graphs
The developer SHALL be able to read call totals for a range of 7, 30 or 90 days, grouped per model, per day and per agent slot: calls, input tokens, output tokens and estimated cost. A call whose gateway reported no tokens SHALL count its estimate, marked as an estimate. A model without a stored price SHALL contribute calls and tokens but no cost, and the totals SHALL say that cost is incomplete. The calls page SHALL draw each grouping as a bar chart above the per-conversation table. The route SHALL sit behind the developer gate.

#### Scenario: Totals per agent
- **WHEN** in the last 7 days the Designer made 3 calls and the Reviewer 1
- **THEN** the per-agent totals give `designer` 3 calls and `reviewer` 1 call, each with its token sums

#### Scenario: Unpriced model
- **WHEN** a model with calls in range has no stored price
- **THEN** its calls and tokens are counted, it has no cost, and the totals are marked cost incomplete

#### Scenario: Range refused
- **WHEN** the range is 45 days
- **THEN** it is refused naming the field

### Requirement: Model prices are shown and refreshed from OpenRouter
The Models page SHALL show, for every registry slug, the input and output price per million tokens and the date they were fetched. The developer SHALL be able to refresh prices; a refresh SHALL make one request to OpenRouter's public model list and store the prices of registry slugs only. A slug the list does not price SHALL show "no price" and SHALL never be given a guessed price. A failed refresh SHALL keep the stored prices and report the failure. Estimated cost SHALL be tokens times the stored price and SHALL be labelled an estimate at the last fetched price. Prices and costs SHALL appear only on developer routes.

#### Scenario: Prices refreshed
- **WHEN** the developer refreshes prices and OpenRouter lists `deepseek/deepseek-v4.1-flash` with prompt and completion prices
- **THEN** the Models page shows that slug's price per million input and output tokens with today's fetch date

#### Scenario: Slug not priced
- **WHEN** OpenRouter's list does not contain `~deepseek/deepseek-v4-flash-latest`
- **THEN** that slug shows "no price"

#### Scenario: Refresh fails
- **WHEN** OpenRouter does not answer
- **THEN** the stored prices stay as they were and the page reports the failure

#### Scenario: Homeowner never sees prices
- **WHEN** the homeowner view is loaded
- **THEN** no price or cost appears in it

### Requirement: The agent workflow is shown as a map
The developer SHALL be able to open a workflow map showing the homeowner, the Foreman and every specialist agent; for each agent its routed model and its enabled plugins; the hand-offs between them; and the points where a confirmation (`interrupt()`) or the render guard stops the flow. The nodes and hand-offs SHALL come from the running graph and the loaded plugin manifests, not from a hand-written list. The route SHALL sit behind the developer gate.

#### Scenario: Map matches routing
- **WHEN** the Designer's slot is routed to `anthropic/claude-haiku-4.5` from the panel
- **THEN** the map shows the Designer node with that model

#### Scenario: Disabled plugin
- **WHEN** a plugin is disabled globally
- **THEN** the map shows it as disabled on its agent

#### Scenario: Guard visible
- **WHEN** the map is loaded
- **THEN** the Builder's render step and the Lighting agent's `final` render are marked as passing the render guard, and package creation and revision are marked as waiting for confirmation

### Requirement: Open owner items are listed
The developer SHALL be able to read every `TODO(user)` marker in the backend code and configuration (tests excluded), each with its file path, line number and the text after the marker, at most 200 items. The list SHALL be read-only and SHALL follow the checked-out files without a separate registry. The route SHALL sit behind the developer gate.

#### Scenario: Open owner items listed
- **WHEN** `backend/config/design_rules.yaml` holds a `TODO(user)` line about `even_tolerance_mm`
- **THEN** the list holds that file, its line number and the text about `even_tolerance_mm`

#### Scenario: Tests excluded
- **WHEN** a test file contains `TODO(user)`
- **THEN** it is not listed
