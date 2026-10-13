## ADDED Requirements

### Requirement: The chat's room measurements match the approved room version
The room block the Foreman and specialists receive for the conversation's confirmed room SHALL state each wall's length and each ceiling height as the inspector view shows them, read from the stored document of the room's approved composition version and labelled with that version number. When the room has no approved version it SHALL use the latest version and say that it is not approved; when it has no composition it SHALL state the house-file figures as today. The block SHALL be rebuilt on every turn, so approving a version changes the figures from the next turn without any action by the owner. The prompt SHALL tell the model to prefer this block over measurements it quoted earlier or that appear in the conversation note.

#### Scenario: Irregular room quoted by wall
- **WHEN** Wohnen version 2 is approved and the owner asks how long the walls are
- **THEN** the reply gives wall 1 to wall 5 as 6200, 5700, 2700, 2241 and 6199 mm and the ceiling as 2500 mm, naming version 2, with no bounding-box figure presented as a wall length

#### Scenario: New version approved
- **WHEN** the owner approves Wohnen version 3, whose wall 3 is 2900 mm, and sends the next message
- **THEN** the room block names version 3 and wall 3 as 2900 mm, and the reply does not repeat version 2's 2700 mm

#### Scenario: No approved version
- **WHEN** Wohnen has versions 1 and 2 and none is approved
- **THEN** the block uses version 2 and states that it is not approved

### Requirement: The chat can read a room version's inspector dimensions
The chat SHALL be able to read the wall lengths and ceiling heights of a named room version, the same figures the inspector view's dimensions switch shows, so that it can confirm or correct a figure the owner or the bot quoted. The read SHALL be read-only, SHALL be limited to the conversation's confirmed room, and SHALL never change a dimension, the house file or a spec.

#### Scenario: Confirm a figure
- **WHEN** the owner says "the inspector shows 2241 on wall 4, you said 2300" about version 2
- **THEN** the bot reads version 2's dimensions, confirms wall 4 is 2241 mm and corrects its earlier figure in the reply

#### Scenario: Other room refused
- **WHEN** the bot is asked for the dimensions of a room outside the conversation's confirmed room
- **THEN** the read is refused with a stated reason and nothing is returned
