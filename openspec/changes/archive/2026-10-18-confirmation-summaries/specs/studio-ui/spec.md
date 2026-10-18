## MODIFIED Requirements

### Requirement: A pending confirmation is answered in the view
When a reply carries a pending confirmation, the view SHALL show it as a card headed "Confirm: <title>", where the title is the confirmation's plain title and never its internal subject. The card SHALL show the summary and proposal, the table of calculations when the confirmation has one, a **Yes** and a **No** button and an optional reason, and SHALL hide the composer until it is answered. Answering SHALL send the owner's answer on the thread and show the reply that follows. Reopening a conversation with a confirmation still pending SHALL show the card again.

#### Scenario: Yes
- **WHEN** the Designer proposes a revision and the owner clicks Yes
- **THEN** the view shows the reply that reports the new version and the composer returns

#### Scenario: No with a reason
- **WHEN** the owner clicks No with "make it 4 shelves"
- **THEN** the reason is sent with the answer and the next reply is shown

#### Scenario: Reopened while pending
- **WHEN** the owner reloads a conversation that has a pending brief confirmation
- **THEN** the card is shown and the composer is hidden

#### Scenario: Plain heading for a room change
- **WHEN** the Designer proposes a room change in `Wohnen`
- **THEN** the card is headed "Confirm: Composing room", shows one table row per placed item, and the text `compose_room` appears nowhere in the view

## ADDED Requirements

### Requirement: An answered confirmation is shown collapsed
The conversation view SHALL show each answered confirmation in the history in its place, framed and aligned like a confirmation, as one compact row: its plain title and the owner's answer ("Yes" or "No"), followed by the reason when one was given. The row SHALL hold a dropdown button. Pressing it SHALL show the summary the owner was shown and, when the confirmation has one, its table of calculations, and pressing it again SHALL hide them. The row SHALL start collapsed, including after a reload, and opening it SHALL NOT send anything or start a turn. The row SHALL NOT show the confirmation's internal subject, a model name, prompt, token count or cost. The view SHALL pass a recorded browser check before it counts as done.

#### Scenario: Room change collapsed
- **WHEN** the owner confirmed a room change in `Wohnen` with Yes
- **THEN** the conversation shows "Composing room · Yes" with a dropdown, and no item rows are visible

#### Scenario: Calculations opened
- **WHEN** the owner opens the dropdown of "Composing room · Yes"
- **THEN** a table lists each placed item with its kind, size, placement, centre and rotation, and the summary's comparison with the previous version is shown below it

#### Scenario: Declined revision with a reason
- **WHEN** the owner answered a revision No with "make it 4 shelves"
- **THEN** the row reads "Revising piece · No — make it 4 shelves" and the dropdown shows the summary with no table

#### Scenario: Collapsed after a reload
- **WHEN** the owner opens a dropdown and reloads the conversation
- **THEN** every answered confirmation is collapsed again
