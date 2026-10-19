## ADDED Requirements

### Requirement: A piece is duplicated from the Pieces page
The piece dialog on the Pieces page SHALL offer "Duplicate piece", asked in place in the same way as "Delete piece". The form asks for:
- the version to copy, from a dropdown of the piece's versions with the latest chosen;
- the copy's name, prefilled as "<piece name> (copy)";
- the copy's id, prefilled from the name made into an id and editable.

"Duplicate" sends the request. "Cancel" closes the form, and nothing is sent. On success, the Pieces list is refreshed and the Studio opens the copy's new conversation. A refusal SHALL be shown in the form with its reason, and the form stays open.

#### Scenario: Duplicate from the dialog
- **WHEN** the owner opens Sideboard's dialog, chooses "Duplicate piece", keeps version 3, names it "Sideboard Hall" and presses "Duplicate"
- **THEN** the copy is created, the Pieces list shows it, and its conversation opens

#### Scenario: Refusal shown
- **WHEN** the id entered is already in use
- **THEN** the form shows the refusal naming the id, and nothing is created

#### Scenario: Cancel
- **WHEN** the owner opens "Duplicate piece" and presses "Cancel"
- **THEN** no request is sent
