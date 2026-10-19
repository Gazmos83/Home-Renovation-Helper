## ADDED Requirements

### Requirement: A whole piece can be deleted
The owner SHALL be able to delete a whole piece through an owner-gated route. Before deleting, the owner SHALL be able to read, through a second owner-gated route that changes nothing, what the delete would remove:
- the piece's versions;
- which of them are approved;
- which have a pricing;
- the conversations bound to the piece;
- the reason the delete would be refused, when it would be.

Deleting a piece SHALL remove:
- every version, as deleting that version removes it (its folder with the input, model, screenshots, views, renders, cut list and drilling list, and its reviews, render runs and their feedback, verdict, pricings, and the notices' references to it);
- the piece's record;
- every conversation bound to the piece, as deleting that conversation removes it: its memory first, then its index entry with its tool settings and upload records, then its upload files.

An approved version SHALL NOT block the delete. Rooms, compositions, preferences, engineering records and generator-extension requests SHALL be unchanged.

The delete SHALL be refused, with nothing removed and the reason given in plain words, when:
- a room composition version places any version of the piece (naming the composition and its version);
- a build or render of any version of the piece is queued or running;
- a turn or a resume is running in one of its conversations;
- the conversations' memory cannot be reached.

A piece that does not exist SHALL answer 404. After a delete, the package id is free: a new piece may take it, and its first version is version 1. No agent tool SHALL delete a piece.

#### Scenario: Piece with an approved version deleted
- **WHEN** `sideboard-1200` has version 1, approved and priced, and one conversation, and the owner deletes the piece
- **THEN** `sideboard-1200` is no longer listed, its folder is gone, its pricing and approval are gone, its conversation answers 404, and no room or composition changed

#### Scenario: What would go
- **WHEN** the owner asks what deleting `listening-wall` would remove, and it has versions 10 to 19 with 19 approved and priced and two conversations
- **THEN** the answer lists the ten versions, version 19 as approved with its pricing, and the two conversations, and nothing is deleted

#### Scenario: Placed in a composition
- **WHEN** composition `Living room` version 3 places `hall-bench` version 2 and the owner deletes `hall-bench`
- **THEN** the delete is refused naming `Living room` version 3, and nothing is removed

#### Scenario: Still building
- **WHEN** the owner deletes a piece whose latest version is still building
- **THEN** the delete is refused saying the piece is still building, and nothing is removed

#### Scenario: Turn running in its conversation
- **WHEN** a turn is running in the piece's conversation and the owner deletes the piece
- **THEN** the delete is refused saying a reply is still being written, and nothing is removed

#### Scenario: Id reused
- **WHEN** `kommode-harmony` with versions 1 and 2 is deleted and a design is then imported as `kommode-harmony`
- **THEN** the new piece's first version is version 1

#### Scenario: Unknown piece
- **WHEN** the owner deletes a piece id that does not exist
- **THEN** the response is 404

#### Scenario: Not signed in
- **WHEN** either route is called without the session cookie
- **THEN** the response is 401
