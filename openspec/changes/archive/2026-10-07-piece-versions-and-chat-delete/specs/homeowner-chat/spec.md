## ADDED Requirements

### Requirement: A conversation can be deleted
The owner SHALL be able to delete a conversation through an owner-gated route. A delete removes, in this order:
1. the conversation's memory in the checkpointer; if that fails, the delete is refused with the memory refusal and nothing else is touched;
2. its index entry, together with its tool settings and upload records;
3. its upload files.

Pieces, versions, renders, rooms, preferences, reviews, render feedback and recorded usage SHALL be unchanged. A delete SHALL be refused with 409, saying a reply is still being written, while a turn or a resume is running on that thread. An unknown thread id SHALL answer 404. A deleted conversation cannot be restored.

#### Scenario: Delete a conversation with a piece
- **WHEN** the owner deletes a thread that created `murphy-bed` versions 1 and 2 and holds two uploads
- **THEN** the thread is gone from the list, reading it answers 404, its uploads answer 404 and their files are gone, and `murphy-bed` with both versions and their renders is still on the Pieces page

#### Scenario: Turn running
- **WHEN** the owner deletes a thread while its turn is still running
- **THEN** the response is 409 saying a reply is still being written, and the thread is unchanged

#### Scenario: Unknown thread
- **WHEN** the owner deletes a thread id that does not exist
- **THEN** the response is 404

#### Scenario: Not signed in
- **WHEN** the delete route is called without the session cookie
- **THEN** the response is 401
