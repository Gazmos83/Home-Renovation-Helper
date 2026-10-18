## ADDED Requirements

### Requirement: A whole piece is deleted from the Pieces page after "Are you sure?"
The piece dialog on the Pieces page SHALL offer "Delete piece", whatever its versions' approval. Pressing it SHALL NOT delete anything yet. It SHALL show, in place, what the delete would remove, read from the service:
- "Are you sure? <piece name> and all its N versions will be deleted with their renders, reviews and pricings.";
- when any version is approved, "Approved: version <n>, priced" (or "not priced") for each approved version;
- when the piece has conversations, "Its M conversation(s) will be deleted too.";
- "This cannot be undone."

It SHALL offer "Yes, delete <piece name>" and "Cancel". When the service says the delete would be refused, the reason SHALL be shown instead of the "Yes" button.

Only "Yes" SHALL send the delete. Afterwards:
- the dialog SHALL close;
- the piece SHALL no longer be on the Pieces page or in its sub-menu;
- its conversations SHALL no longer be in the conversation list.

A refusal returned by the delete SHALL be shown with its reason next to the control, and the piece SHALL stay listed.

#### Scenario: Confirmed delete
- **WHEN** the owner opens `sideboard-1200`, presses "Delete piece", reads that version 1 is approved and priced and that one conversation goes too, and presses "Yes, delete Sideboard"
- **THEN** the dialog closes, `sideboard-1200` is gone from the Pieces page and its sub-menu, and its conversation is gone from the conversation list

#### Scenario: Cancelled
- **WHEN** the owner presses "Delete piece" and then "Cancel"
- **THEN** nothing is deleted and "Delete piece" is shown again

#### Scenario: Refusal shown before confirming
- **WHEN** the owner presses "Delete piece" for a piece a composition places
- **THEN** the reason naming the composition is shown, no "Yes" button is offered, and the piece stays listed
