## ADDED Requirements

### Requirement: The Workspace's piece and room panes approve the version they show
The Workspace's piece pane SHALL show, for the piece version it shows, whether that version is approved, and the room pane SHALL do the same for the composition version it shows. Each pane SHALL offer "Approve version N" when the shown version's build succeeded and it is not approved, and "Unapprove version N" when the shown version is the approved one. Neither control SHALL be offered for a version that is not built. Approving the shown version SHALL replace any other approved version of the same piece or composition. An API refusal SHALL be shown in plain words next to the control, and the version's state SHALL stay as it was. After a change, the pane, its version dropdown, the Piece and Project flyouts, the Pieces page and the Rooms page SHALL show the new state without a reload. Neither pane SHALL show a model name, prompt, token count or cost. Approving or unapproving SHALL NOT start a turn. The flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Approve the shown piece version
- **WHEN** the piece pane shows `hall-bench` version 2, which is built and not approved, and the owner presses "Approve version 2"
- **THEN** the pane shows version 2 as approved, the version dropdown labels version 2 "approved", and the Piece flyout shows version 2 approved

#### Scenario: Approve an older piece version from the dropdown
- **WHEN** `hall-bench` version 3 is approved, the owner chooses version 2 in the piece pane's dropdown and presses "Approve version 2"
- **THEN** version 2 is approved and version 3 is no longer approved

#### Scenario: Unapprove the shown piece version
- **WHEN** the piece pane shows approved `hall-bench` version 2 and the owner presses "Unapprove version 2"
- **THEN** the pane shows that version 2 is not approved and offers "Approve version 2"

#### Scenario: Unbuilt version offers no control
- **WHEN** the piece pane shows `hall-bench` version 4 while it is still building
- **THEN** the pane offers neither "Approve version 4" nor "Unapprove version 4"

#### Scenario: Approve the shown room version
- **WHEN** the room pane shows `Hall` version 2, which is built and not approved, and the owner presses "Approve version 2"
- **THEN** the pane shows version 2 as approved, its dropdown labels version 2 "(approved)", and the Project panel shows `Hall` version 2 approved

#### Scenario: Room approval refused
- **WHEN** the owner approves `Hall` version 2 from the room pane while it places a piece version that is not approved
- **THEN** the refusal naming that piece is shown next to the control and version 2 stays unapproved

#### Scenario: Approval does not start a turn
- **WHEN** the owner approves a version from either pane
- **THEN** no message is sent to the conversation and the composer stays usable
