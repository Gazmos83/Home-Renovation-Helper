## ADDED Requirements

### Requirement: The Rooms page duplicates a room
The room dialog on the Measured Rooms page SHALL offer "Duplicate room", asked in place like "Delete room". It SHALL show a name field prefilled with "<name> (copy)" and, when the room has a composition, a layout choice listing its versions newest first, with the latest preselected, and "No layout". Duplicate SHALL create the copy and Cancel SHALL close the form without change. A refusal SHALL be shown in plain words under the form, and the form SHALL stay open. After a duplicate, the rooms list SHALL show the new room.

#### Scenario: Duplicate with the latest layout
- **WHEN** the owner opens `Wohnen`, chooses "Duplicate room", keeps "Wohnen (copy)" and the preselected latest version, and confirms
- **THEN** the rooms list shows "Wohnen (copy)", and its dialog shows its composition at version 1 building

#### Scenario: Room without a composition
- **WHEN** the owner chooses "Duplicate room" for a room with no composition
- **THEN** the form shows the name field only, with no layout choice

#### Scenario: Refused
- **WHEN** the owner duplicates `Wohnen` with a name another room has
- **THEN** the refusal is shown under the form, the form stays open, and the list is unchanged
