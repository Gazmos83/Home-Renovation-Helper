## ADDED Requirements

### Requirement: Room-version approval is shown and set from the Studio
The Studio SHALL show, on the Rooms page for the chosen composition version and in a conversation's Project panel for the confirmed room's composition, whether a version is approved, and SHALL let the owner approve a built version and unapprove an approved one there. The control SHALL be offered only for a version whose build succeeded; an API refusal SHALL be shown next to the version it names. After a change the page and the panel SHALL show the new state without a reload. Neither SHALL show a model name, prompt, token count or cost. The approve and unapprove flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Approve from the Rooms page
- **WHEN** the owner opens composition `Wohnen` on the Rooms page, chooses version 2, and approves it
- **THEN** version 2 shows "Approved" and a reload shows the same

#### Scenario: Approval in the project panel
- **WHEN** the conversation's confirmed room is `Hall`, version 1 is approved and version 2 is the latest built version
- **THEN** the Project panel shows version 2 as latest and version 1 as approved, with a control to approve version 2

#### Scenario: Unapprove
- **WHEN** the owner unapproves `Wohnen` version 2 from the Rooms page
- **THEN** the page and the Project panel show no approved version of `Wohnen`

#### Scenario: Unapprove of a placed piece is explained
- **WHEN** the owner unapproves `listening-wall` v4 from the Pieces page or the Project panel while approved `Wohnen` version 2 places it
- **THEN** the refusal naming `Wohnen` version 2 is shown next to the control and v4 stays approved

### Requirement: A composition version is deleted from the Rooms page and the Project panel after "Are you sure?"
The Rooms page SHALL offer "Delete version N" for the version shown. The Project panel SHALL offer "Delete version N" for the latest composition version. Neither SHALL offer it for an approved version.

Pressing it SHALL NOT delete anything yet. It SHALL show, in place, "Are you sure? Version N and its model and renders will be deleted. This cannot be undone." with "Yes, delete version N" and "Cancel" buttons. When N is the composition's only version, the question SHALL say that the composition will be deleted and the measured room kept.

Only "Yes" SHALL send the delete. Afterwards the Rooms page SHALL show the remaining versions, or drop the composition when it has none left, and the Project panel SHALL refresh. A refusal SHALL be shown with its reason next to the control.

#### Scenario: Confirmed delete on the Rooms page
- **WHEN** the owner shows `Wohnen` version 2, presses "Delete version 2", then "Yes, delete version 2"
- **THEN** version 2 is no longer among the composition's versions and the page shows another version

#### Scenario: Cancelled
- **WHEN** the owner presses "Delete version 2" and then "Cancel"
- **THEN** nothing is deleted and the delete control is shown again

#### Scenario: Approved version has no delete
- **WHEN** the owner shows `Wohnen` version 4, which is approved
- **THEN** no "Delete version 4" control is shown

#### Scenario: Refusal shown
- **WHEN** the owner confirms deleting a composition version that is still building
- **THEN** the refusal is shown next to the control and the version stays listed
