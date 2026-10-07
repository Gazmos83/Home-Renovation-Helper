## ADDED Requirements

### Requirement: Conversations are deleted from the list
Each entry on the Conversations page SHALL offer a delete action. It asks for confirmation, naming the conversation and stating that its pieces and renders are kept and that the conversation cannot be restored. A confirmed delete removes the entry without a reload; a cancel changes nothing. A refusal (a reply still being written, or memory unavailable) SHALL be shown in words next to the entry, which stays. The delete flow SHALL pass a recorded browser check before it counts as done.

#### Scenario: Delete with confirmation
- **WHEN** the owner chooses delete on "Hall shoe bench" and confirms
- **THEN** the entry disappears from the list and the piece is still on the Pieces page

#### Scenario: Cancel
- **WHEN** the owner chooses delete and then cancels
- **THEN** nothing is sent and the entry stays

#### Scenario: Refused while a reply is written
- **WHEN** the owner confirms a delete while that conversation's turn is running
- **THEN** the entry stays and the refusal is shown next to it
