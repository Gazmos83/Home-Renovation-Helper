## REMOVED Requirements

### Requirement: Agent and model pages are tabs of one AI & Agent Settings page
**Reason**: The owner folded the AI & Agent Settings page into the Design Studio (2026-10-14). Its eight tabs become the views of a developer-only Design Studio tab, which keeps the developer route tree's addresses and gate.
**Migration**: See "Agent and model pages are views of the Design Studio's AI & Agent Settings tab". `/admin/agents/<tab>` addresses are unchanged. The header's "AI & Agent Settings" entry is replaced by the tab on the Design Studio rail.

## ADDED Requirements

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
