## ADDED Requirements

### Requirement: Guidelines, engineering knowledge and design rules are views of the Design Studio's Design Knowledge tab
Behind the developer gate, the Design Studio SHALL have a "Design Knowledge" tab, shown below the divider after the AI & Agent Settings tab, with three views, in this order: "Guidelines", "Engineering Knowledge" and "Design Rules", chosen from its sub-menu. The Guidelines view SHALL hold, each under its own heading, the guideline PDF upload with the list of guideline sources, the guideline notes, and the Hardware data section. The Engineering Knowledge view SHALL show what the Engineering knowledge page showed, and the Design Rules view what the Design rules page showed, including its open items. The views SHALL stay on the developer route tree: each SHALL have its own address (`/admin/design-knowledge/guidelines`, `/admin/design-knowledge/engineering`, `/admin/design-knowledge/rules`), and opening that address SHALL show the Design Studio with this tab and that view chosen. `/admin/design-knowledge`, and an `/admin/design-knowledge/` address naming no known view, SHALL show the Guidelines view. Only the chosen view's content SHALL be shown. The old addresses `/guidelines` and `/admin/guidelines` SHALL open the Guidelines view, `/admin/knowledge` the Engineering Knowledge view and `/admin/rules` the Design Rules view. The header SHALL NOT show "Guidelines", "Knowledge" or "Rules" entries, for the owner or the developer. Without the developer gate, the tab SHALL NOT be shown on the rail, and its addresses and the old addresses SHALL open the Workspace tab. The tab SHALL pass a recorded browser check, at 1280 × 800 and at 360 × 780, before it counts as done.

#### Scenario: Guidelines first
- **WHEN** the developer chooses "Design Knowledge" on the Design Studio rail
- **THEN** the address is `/admin/design-knowledge`, the sub-menu shows the three views with "Guidelines" chosen, and the PDF upload with the source list, the guideline notes and the Hardware data section are shown

#### Scenario: View chosen
- **WHEN** the developer chooses "Design Rules" in the sub-menu
- **THEN** the address is `/admin/design-knowledge/rules`, the design rules and open items are shown, and no other view's content is

#### Scenario: View address reloaded
- **WHEN** the developer reloads `/admin/design-knowledge/engineering`
- **THEN** the Design Studio opens with the Design Knowledge tab and its Engineering Knowledge view chosen

#### Scenario: Old addresses
- **WHEN** the developer opens bookmarks to `/guidelines`, `/admin/guidelines`, `/admin/knowledge` and `/admin/rules`
- **THEN** the Design Studio opens with the Guidelines, Guidelines, Engineering Knowledge and Design Rules view chosen respectively

#### Scenario: Sub-menu on a phone
- **WHEN** the developer opens `/admin/design-knowledge/rules` on a 360 × 780 screen
- **THEN** the three views are a row of tabs above the content, with "Design Rules" chosen, and the page itself does not scroll sideways

#### Scenario: Not a developer
- **WHEN** the owner without the developer gate opens `/guidelines` or `/admin/design-knowledge/guidelines`
- **THEN** the Workspace tab opens, the rail shows no "Design Knowledge" tab, and the header shows no "Guidelines" entry

## MODIFIED Requirements

### Requirement: Agent and model pages are views of the Design Studio's AI & Agent Settings tab
Behind the developer gate, the Design Studio SHALL have an "AI & Agent Settings" tab, shown below a divider after the owner tabs, with eight views, in this order: "Agent Memory", "Agent Workflow", "Agent Calls", "Render Offload", "Agent Score", "Token Usage", "Plugins" and "Models and Routing", chosen from its sub-menu. They SHALL show what the Memory, Workflow, Calls, Offload, Feedback, Usage, Plugins and Models pages showed. The views SHALL stay on the developer route tree: each SHALL have its own address (`/admin/agents/memory`, `/admin/agents/workflow`, `/admin/agents/calls`, `/admin/agents/offload`, `/admin/agents/score`, `/admin/agents/usage`, `/admin/agents/plugins`, `/admin/agents/models`), and opening that address SHALL show the Design Studio with this tab and that view chosen. `/admin/agents`, and an `/admin/agents/` address naming no known view, SHALL show the Agent Memory view. Only the chosen view's content SHALL be shown. The old addresses `/admin/memory`, `/admin/workflow`, `/admin/conversations`, `/admin/offload`, `/admin/feedback`, `/admin/usage`, `/admin/plugins` and `/admin/models` SHALL open the matching view. The header SHALL NOT show developer entries: no "AI & Agent Settings", "Guidelines", "Knowledge", "Rules", "Models", "Plugins", "Usage", "Feedback", "Offload", "Calls", "Workflow" or "Memory" entries. Without the developer gate, the tab SHALL NOT be shown on the rail, and its addresses SHALL open the Workspace tab. The tab SHALL pass a recorded browser check, at 1280 × 800 and at 360 × 780, before it counts as done.

#### Scenario: Agent Memory first
- **WHEN** the developer chooses "AI & Agent Settings" on the Design Studio rail
- **THEN** the address is `/admin/agents`, the sub-menu shows the eight views with "Agent Memory" chosen, and the memory settings are shown

#### Scenario: View chosen
- **WHEN** the developer chooses "Token Usage" in the sub-menu
- **THEN** the address is `/admin/agents/usage`, token usage is shown, and no other view's content is

#### Scenario: View address reloaded
- **WHEN** the developer reloads `/admin/agents/offload`
- **THEN** the Design Studio opens with the AI & Agent Settings tab and its Render Offload view chosen

#### Scenario: Old address
- **WHEN** the developer opens a bookmark to `/admin/conversations`
- **THEN** the Design Studio opens with the Agent Calls view chosen

#### Scenario: Navigation
- **WHEN** the developer is signed in and looks at the header navigation
- **THEN** it shows "Design Studio" and "Help" only, with no developer entries

#### Scenario: Sub-menu on a phone
- **WHEN** the developer opens `/admin/agents/models` on a 360 × 780 screen
- **THEN** the eight views are a row of tabs above the content that scrolls sideways, with "Models and Routing" chosen, and the page itself does not scroll sideways

#### Scenario: Not a developer
- **WHEN** the owner without the developer gate opens `/admin/agents/models`
- **THEN** the Workspace tab opens, and the rail shows no "AI & Agent Settings" tab
