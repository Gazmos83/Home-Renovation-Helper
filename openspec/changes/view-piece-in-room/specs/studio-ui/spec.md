## ADDED Requirements

### Requirement: The placement question opens the Room layout
A pending question set that asks where to place a piece SHALL show a "Room layout" button with its first question. Pressing it SHALL switch the Workspace to the "Chat and room" layout, keep the question set open with its answers so far, and send nothing. On a narrow screen it SHALL show the room pane. When the room has no 3D view yet, the room pane SHALL say so as it does today, and the wall choices with their lengths remain the guide.

#### Scenario: Room layout from the question
- **WHEN** the placement question is pending in the "Chat and piece" layout and the owner presses "Room layout"
- **THEN** the layout is "Chat and room", the room pane shows `Wohnen` with its labelled walls, and the question is still pending

#### Scenario: Other question sets
- **WHEN** a question set that is not about placement is pending
- **THEN** no "Room layout" button is shown
