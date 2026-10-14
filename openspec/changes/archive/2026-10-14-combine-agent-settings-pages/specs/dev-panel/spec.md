## ADDED Requirements

### Requirement: Agent and model pages are tabs of one AI & Agent Settings page
Behind the developer gate, the Studio SHALL have an AI & Agent Settings page at `/admin/agents` with the page title "AI & Agent Settings" and eight tabs, in this order: "Agent Memory", "Agent Workflow", "Agent Calls", "Render Offload", "Agent Score", "Token Usage", "Plugins" and "Models and Routing". They SHALL show what the Memory, Workflow, Calls, Offload, Feedback, Usage, Plugins and Models pages showed. Each tab SHALL have its own address — `/admin/agents/memory`, `/admin/agents/workflow`, `/admin/agents/calls`, `/admin/agents/offload`, `/admin/agents/score`, `/admin/agents/usage`, `/admin/agents/plugins`, `/admin/agents/models` — and opening that address SHALL show the page with that tab chosen. `/admin/agents`, and an `/admin/agents/` address naming no known tab, SHALL show the Agent Memory tab. The tabs SHALL be a rail at the screen's left edge below the header, with the same font, icon style, colour scheme and "Hide labels" switch as the conversation page's panel rail and the Pricing Overview rail: each tab an icon, with its label beside it while labels are shown, the chosen tab highlighted, and the switch at the rail's foot. The label choice SHALL be shared with those rails; a browser that cannot store it SHALL show the labels hidden. The tabs SHALL be exposed as a vertical tab list with the chosen tab marked selected, and only the chosen tab's content SHALL be shown. The old addresses `/admin/memory`, `/admin/workflow`, `/admin/conversations`, `/admin/offload`, `/admin/feedback`, `/admin/usage`, `/admin/plugins` and `/admin/models` SHALL open the matching tab. The developer navigation SHALL show one "AI & Agent Settings" entry, marked current on every tab, and SHALL NOT show "Models", "Plugins", "Usage", "Feedback", "Offload", "Calls", "Workflow" or "Memory" entries; "Guidelines", "Knowledge" and "Rules" SHALL keep their own entries. Without the developer gate the page and its tabs SHALL NOT be shown. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Agent Memory first
- **WHEN** the developer chooses "AI & Agent Settings" in the navigation
- **THEN** the page opens with the Agent Memory tab chosen and the memory settings shown

#### Scenario: Tab chosen
- **WHEN** the developer chooses the Token Usage tab
- **THEN** the address is `/admin/agents/usage`, token usage is shown, and no other tab's content is

#### Scenario: Labels shown
- **WHEN** the developer chooses "Show labels" on the AI & Agent Settings rail
- **THEN** each tab shows its label beside its icon, and the conversation and Pricing Overview rails show their labels too until the developer hides them

#### Scenario: Tab address reloaded
- **WHEN** the developer reloads `/admin/agents/offload`
- **THEN** the page opens with the Render Offload tab chosen

#### Scenario: Old address
- **WHEN** the developer opens a bookmark to `/admin/conversations`
- **THEN** the page opens with the Agent Calls tab chosen

#### Scenario: Navigation
- **WHEN** the developer is signed in and looks at the navigation
- **THEN** it shows "AI & Agent Settings", "Guidelines", "Knowledge" and "Rules", and none of the eight former entries

#### Scenario: Not a developer
- **WHEN** the owner without the developer gate opens `/admin/agents/models`
- **THEN** the Pieces page opens and no tab is shown
