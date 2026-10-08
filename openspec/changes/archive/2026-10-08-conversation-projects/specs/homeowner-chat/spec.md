## MODIFIED Requirements

### Requirement: A turn binds the thread to the piece it creates or revises
When a confirmed action creates a piece or revises one, the thread SHALL be bound to that piece, replacing any earlier binding, so the thread's list entry and later turns name the piece last worked on; the piece SHALL join the conversation's builds if it is not one already and becomes the active build. When the owner's message names exactly one build of the conversation, or one house-file piece, other than the active build, that piece SHALL become the active build at the start of the turn, joining the builds if needed. A declined or failed action SHALL bind nothing. Switching the active build SHALL change no piece, version or room.

#### Scenario: Created in the conversation
- **WHEN** the owner confirms a new piece `hall-bench` on a thread started without a piece
- **THEN** reading the thread shows it is about `hall-bench`, and the thread list shows the same

#### Scenario: Revised on an unbound thread
- **WHEN** the owner confirms a revision of `hall-bench` on a thread with no piece
- **THEN** the thread is about `hall-bench`

#### Scenario: A second piece
- **WHEN** a thread about `hall-bench` has a confirmed new piece `shelf`
- **THEN** the thread is about `shelf` from then on, and its builds are `hall-bench` and `shelf`

#### Scenario: Declined
- **WHEN** the owner answers `no` to a new piece
- **THEN** the thread's piece and builds are unchanged

#### Scenario: Switch by name
- **WHEN** a thread about `shelf` also holds `hall-bench` and the owner writes "back to the hall bench: make it 900 mm"
- **THEN** the turn runs with `hall-bench` as the active build and the thread is about `hall-bench`

#### Scenario: Turntable published
- **WHEN** the latest version's draft turntable has finished
- **THEN** the progress names its viewer by its package route; before it finishes the viewer is null
