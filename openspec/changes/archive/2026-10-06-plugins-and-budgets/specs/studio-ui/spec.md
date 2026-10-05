## ADDED Requirements

### Requirement: Conversations show their tool toggles
The Studio SHALL list the owner's conversations and, for each, its toggleable tools by plain name and description with their on/off state, letting the owner switch them; tools that cannot be toggled SHALL be shown as always on. The page SHALL NOT show model names, token counts or costs.

#### Scenario: Toggle a tool
- **WHEN** the owner switches off the room check in one conversation
- **THEN** the page shows it off for that conversation and the next turn there binds no `room_fit`

### Requirement: The developer panel has its own pages
The Studio SHALL show the developer pages — models and routing, generation and token restrictions, plugins with invocations, usage per day — on a separate route tree that is reachable only when the developer API answers, and SHALL show an API refusal (a failed probe, an out-of-range value) next to the field it names. Each page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Panel disabled
- **WHEN** the developer panel is disabled
- **THEN** the developer pages are not reachable and no link to them is shown
