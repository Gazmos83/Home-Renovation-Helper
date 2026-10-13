## ADDED Requirements

### Requirement: Open review items in the context follow the current version
The open review items placed in a conversation's context SHALL come from the newest review of the piece's current version, which is its approved version when one is approved and otherwise its latest version. Items of a review of any other version SHALL NOT be placed in the context, and each item shown SHALL name the version it is about. When the current version has no review, no review items SHALL be shown. The reviews and their items SHALL NOT be deleted, edited or closed by this, and approving or unapproving a version SHALL change what is shown from the next turn.

#### Scenario: A review of an older version is not shown
- **WHEN** version 1 has a review with an open item expecting a width of 1200 mm, and version 3 is approved with no review
- **THEN** the context carries no review items

#### Scenario: The approved version's review is shown, labelled
- **WHEN** version 3 is approved and its review has one open item
- **THEN** the context lists that item and says it is about version 3, and shows no item of the newer review of version 4 if one exists

#### Scenario: No approved version
- **WHEN** no version is approved and the latest version, 2, has a review with two open items
- **THEN** the context lists those two items, labelled version 2

#### Scenario: Approval changes the next turn
- **WHEN** the owner approves version 1 after version 2 was reviewed
- **THEN** the next turn's context shows version 1's review items and not version 2's

#### Scenario: Nothing is deleted
- **WHEN** an older version's review is no longer shown
- **THEN** it and its items are still stored, with their statuses unchanged
