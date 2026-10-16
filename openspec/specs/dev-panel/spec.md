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

### Requirement: Memory settings are edited by the developer
The developer SHALL be able to read, set and reset the memory settings:
- compression: trigger share of the usable context budget (50–100 %), recent turns always kept (0–20), note length (100–2000 tokens), note headings and instructions (text up to 2000 characters), tool-result cut length (0–2000 characters);
- saving: preferences from a brief saved or not (review confirmation is deferred);
- the conversation's slice: other builds as one line or hidden; preferences, latest review items and open generator-extension requests included or left out; render ratings 0–10.

Each setting SHALL show its default, and resetting SHALL restore it. An out-of-range value SHALL be refused naming the field. The page SHALL also list the fixed rules no setting changes: rooms enter a conversation only by confirmation, nothing from another conversation is given, generator-extension requests are always saved, and the note's safety rules are composed in code. Changes SHALL apply from the next call, without a restart. The route SHALL sit behind the developer gate.

#### Scenario: Trigger lowered
- **WHEN** the developer sets the trigger share to 75 %
- **THEN** the setting is stored and the next call compresses at 75 % of the usable budget

#### Scenario: Out of range
- **WHEN** the developer sets recent turns always kept to 50
- **THEN** it is refused naming the field and the stored value is unchanged

#### Scenario: Reset
- **WHEN** the developer resets the note length
- **THEN** it is 400 tokens again

#### Scenario: Panel disabled
- **WHEN** the panel is disabled and the memory route is called with a valid session
- **THEN** the response is 404

### Requirement: Developer manages engineering source rights and verification
Behind the developer gate, the developer SHALL list/register engineering metadata and files, inspect current rights decisions, approve/revoke documented operation scopes, review technical verification, ingest/re-ingest approved content and inspect failures/metadata-only reasons. Rights and technical verification SHALL be displayed separately. Engineering upload/registration SHALL NOT index immediately on a licence note. A locally supplied large document SHALL have a confined ingestion path even when it exceeds the browser upload cap, without silently changing that cap.

#### Scenario: Engineering source registered pending
- **WHEN** a developer registers a manufacturer manual without rights evidence
- **THEN** the page shows pending/link-only with no searchable excerpt

#### Scenario: Panel disabled
- **WHEN** the developer panel is disabled and an engineering administration route is requested with a valid session
- **THEN** the response is 404

#### Scenario: No session
- **WHEN** an engineering source approval route is requested without the owner session
- **THEN** the response is 401 and no approval is recorded

### Requirement: Developer manages typed numerical evidence without automatic verification
The developer SHALL create/review numerical records with product identity, canonical/original units, value basis, range/conditions and source/page. Invalid units, missing provenance for a supplied value or product mismatches SHALL be refused naming the field. Candidate values SHALL stay unverified until explicit technical review. No shipped material/anchor capacity SHALL be invented to make the catalogue appear complete.

#### Scenario: Property lacks provenance
- **WHEN** a developer supplies an elasticity value with no source revision/page
- **THEN** the save is refused naming provenance and the verified property remains unchanged

#### Scenario: Candidate saved
- **WHEN** an extracted value is saved as a review candidate
- **THEN** it is labelled unverified and cannot satisfy a verified engineering input

### Requirement: Agent and model pages are views of the Design Studio's AI & Agent Settings tab
Behind the developer gate, the Design Studio SHALL have an "AI & Agent Settings" tab, shown below a divider after the owner tabs, with eight views, in this order: "Agent Memory", "Agent Workflow", "Agent Calls", "Render Offload", "Agent Score", "Token Usage", "Plugins" and "Models and Routing", chosen from its sub-menu. They SHALL show what the Memory, Workflow, Calls, Offload, Feedback, Usage, Plugins and Models pages showed. The views SHALL stay on the developer route tree: each SHALL have its own address (`/admin/agents/memory`, `/admin/agents/workflow`, `/admin/agents/calls`, `/admin/agents/offload`, `/admin/agents/score`, `/admin/agents/usage`, `/admin/agents/plugins`, `/admin/agents/models`), and opening that address SHALL show the Design Studio, titled "Design Studio", with this tab and that view chosen. `/admin/agents`, and an `/admin/agents/` address naming no known view, SHALL show the Agent Memory view. Only the chosen view's content SHALL be shown. The old addresses `/admin/memory`, `/admin/workflow`, `/admin/conversations`, `/admin/offload`, `/admin/feedback`, `/admin/usage`, `/admin/plugins` and `/admin/models` SHALL open the matching view. The developer navigation in the header SHALL show "Guidelines", "Knowledge" and "Rules", and SHALL NOT show "AI & Agent Settings", "Models", "Plugins", "Usage", "Feedback", "Offload", "Calls", "Workflow" or "Memory" entries. Without the developer gate, the tab SHALL NOT be shown on the rail, and its addresses SHALL open the Pieces tab. The tab SHALL pass a recorded browser check, at 1280 × 800 and at 360 × 780, before it counts as done.

#### Scenario: Agent Memory first
- **WHEN** the developer chooses "AI & Agent Settings" on the Design Studio rail
- **THEN** the address is `/admin/agents`, the sub-menu shows the eight views with "Agent Memory" chosen, and the memory settings are shown

#### Scenario: View chosen
- **WHEN** the developer chooses "Token Usage" in the sub-menu
- **THEN** the address is `/admin/agents/usage`, token usage is shown, and no other view's content is

#### Scenario: View address reloaded
- **WHEN** the developer reloads `/admin/agents/offload`
- **THEN** the Design Studio opens with the AI & Agent Settings tab and its Render Offload view chosen, and "Design Studio" is marked current in the header

#### Scenario: Old address
- **WHEN** the developer opens a bookmark to `/admin/conversations`
- **THEN** the Design Studio opens with the Agent Calls view chosen

#### Scenario: Navigation
- **WHEN** the developer is signed in and looks at the header navigation
- **THEN** the developer entries are "Guidelines", "Knowledge" and "Rules", and there is no "AI & Agent Settings" entry

#### Scenario: Sub-menu on a phone
- **WHEN** the developer opens `/admin/agents/models` on a 360 × 780 screen
- **THEN** the eight views are a row of tabs above the content that scrolls sideways, with "Models and Routing" chosen, and the page itself does not scroll sideways

#### Scenario: Not a developer
- **WHEN** the owner without the developer gate opens `/admin/agents/models`
- **THEN** the Pieces tab opens, and the rail shows no "AI & Agent Settings" tab
