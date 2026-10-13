## MODIFIED Requirements

### Requirement: Deleting a version removes its records
When the owner deletes a piece version, the house file SHALL remove, in the same transaction:
- the version record;
- every review of that version and its items;
- every render run of that version and the feedback on it;
- every pricing of that version.

The render notices in the piece's conversations that name that version SHALL keep their text, but SHALL no longer name the piece or the version, so they show no button. Records of other versions SHALL be unchanged. If removing the version's folder fails, the records SHALL stay as they were and the delete SHALL be reported as failed.

When the deleted version was the piece's last, the house file SHALL also:
- remove the piece;
- clear the piece from every conversation it was bound to (the active piece and the conversation's list of builds).

The conversations themselves and their messages SHALL stay. Generator-extension requests naming the piece SHALL stay.

#### Scenario: Records of the deleted version go
- **WHEN** `hall-bench` version 2 has a review with two items, a rated draft render and a pricing, and the owner deletes version 2
- **THEN** the house file holds no review, item, render run, feedback or pricing for `hall-bench` version 2, and those of version 3 are unchanged

#### Scenario: Notice loses its button
- **WHEN** a conversation holds a "draft turntable of hall-bench version 2 is ready" notice and the owner deletes version 2
- **THEN** the notice is still shown with its text and has no Review button

#### Scenario: Last version unbinds the conversation
- **WHEN** the conversation "Hall bench" is bound to `hall-bench`, which has only version 1, and the owner deletes version 1
- **THEN** the piece is gone, the conversation is still listed with its messages, and its Piece panel shows no piece
