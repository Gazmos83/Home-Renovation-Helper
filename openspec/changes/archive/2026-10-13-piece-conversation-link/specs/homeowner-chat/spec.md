## MODIFIED Requirements

### Requirement: Threads are started, listed and read
The owner SHALL be able to start a conversation (optionally naming the piece it is about, and with or without a title), list conversations, read one conversation's messages and pending item, rename a conversation, and delete one. A thread id SHALL be issued by the service, never chosen by the client, and every thread route SHALL require the owner's session. Starting a conversation that names an existing piece SHALL bind that thread to the piece at once. Starting a conversation for a piece that already has a conversation SHALL be refused, naming that the piece already has a conversation. A thread started without a title SHALL be given one after its first answered turn, written by the Foreman slot's model in three to six words from the owner's first message; the call SHALL be counted against that model's token budget like any other, and when it is refused or fails the title SHALL be the first words of the owner's message (at most 60 characters, cut at a word boundary). A title the owner has set SHALL never be replaced. Deleting a thread SHALL remove its index entry, its conversation memory, its tool settings, its uploads and its summary, and SHALL leave pieces, versions, rooms, preferences, reviews and recorded usage unchanged. A delete SHALL be refused, saying a reply is still being written, while a turn runs on the thread.

#### Scenario: Start and read
- **WHEN** the owner starts a thread and sends one turn
- **THEN** reading the thread returns the owner's message, the reply and nothing pending

#### Scenario: Start bound to an existing piece
- **WHEN** the owner starts a thread naming `hall-bench` and that piece has no conversation yet
- **THEN** reading the thread shows it is about `hall-bench`

#### Scenario: Piece already has a conversation
- **WHEN** `hall-bench` already has a conversation and the owner starts a thread naming `hall-bench`
- **THEN** the start is refused saying the piece already has a conversation, and no new thread is created

#### Scenario: Not signed in
- **WHEN** a thread route is called without the session cookie
- **THEN** the response is 401

#### Scenario: Title from the first message
- **WHEN** the owner starts a thread with no title and sends "I want a listening wall for my records in the living room"
- **THEN** after the reply the thread has a title of three to six words from the Foreman's model, and listing conversations shows it

#### Scenario: Title call refused
- **WHEN** the Foreman's model has reached its daily ceiling when the first turn of an untitled thread ends, and the owner's first message was "I want a listening wall for my records in the living room next to the window"
- **THEN** the thread's title is "I want a listening wall for my records in the living room", the message cut at a word boundary to at most 60 characters, and the turn's reply is unaffected

#### Scenario: Rename
- **WHEN** the owner renames a thread to "Listening wall"
- **THEN** the thread shows "Listening wall", and no later turn changes it

#### Scenario: Delete a conversation with a piece
- **WHEN** the owner deletes a thread that created `listening-wall` versions 1 to 4 and holds two uploads
- **THEN** reading it answers 404, its uploads are no longer served, and `listening-wall` with all four versions is still in the house file and on the Pieces page

#### Scenario: Unknown thread
- **WHEN** the owner deletes or renames a thread id that does not exist
- **THEN** the response is 404

### Requirement: A turn binds the thread to the piece it creates or revises
When a confirmed action creates a piece or revises one on a thread with no bound piece, the thread SHALL be bound to that piece, so the thread's list entry and later turns name it. When the thread is already bound to a piece, a confirmed action that would create a different piece, or revise a different piece, SHALL be refused in plain words naming the bound piece, and SHALL change no binding. Naming another house-file piece in the owner's message SHALL NOT bind the thread to it or switch the piece. A declined or failed action SHALL bind nothing.

#### Scenario: Created in the conversation
- **WHEN** the owner confirms a new piece `hall-bench` on a thread started without a piece
- **THEN** reading the thread shows it is about `hall-bench`

#### Scenario: Revised on an unbound thread
- **WHEN** the owner confirms a revision of `hall-bench` on a thread with no piece
- **THEN** the thread is about `hall-bench`

#### Scenario: A second piece
- **WHEN** a thread about `hall-bench` would confirm a new piece `shelf`
- **THEN** the action is refused naming that the conversation is about `hall-bench`, the thread stays about `hall-bench`, and no second build is recorded

#### Scenario: Declined
- **WHEN** the owner answers `no` to a new piece
- **THEN** the thread's piece is unchanged

#### Scenario: Switch by name
- **WHEN** a thread about `hall-bench` has the owner write "back to the shoe rack: make it 900 mm" naming `shoe-rack`
- **THEN** the thread stays about `hall-bench` and `shoe-rack` is not bound

#### Scenario: Turntable published
- **WHEN** the latest version's draft turntable has finished
- **THEN** the progress names its viewer by its package route; before it finishes the viewer is null
