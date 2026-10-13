## ADDED Requirements

### Requirement: Opening an inspector from the Project flyout closes the flyout
When the owner chooses "Inspect version N" or "Inspect <room>" in the Project flyout, the conversation view SHALL close the flyout and show the inspector beside the chat. Other actions in the flyout (approve, unapprove, delete, using a look) SHALL leave it open, and the Tools and Decisions so far flyouts SHALL not be affected. Reopening the Project icon SHALL open the flyout again with the inspector still shown.

#### Scenario: Inspecting a version closes the flyout
- **WHEN** the owner opens the Project flyout and presses "Inspect version 1"
- **THEN** the flyout is closed and the inspector for version 1 is shown beside the chat

#### Scenario: Inspecting the room closes the flyout
- **WHEN** the owner presses "Inspect Hall" in the Project flyout
- **THEN** the flyout is closed and the room view is shown beside the chat

#### Scenario: Other actions keep it open
- **WHEN** the owner approves a version in the Project flyout
- **THEN** the flyout stays open
