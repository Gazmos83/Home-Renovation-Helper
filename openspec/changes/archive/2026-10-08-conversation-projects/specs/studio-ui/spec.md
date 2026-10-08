## ADDED Requirements

### Requirement: The Pieces page shows and sets each piece's room
The Pieces page SHALL show each piece's room, or "No room" for an unassigned piece, and a room selector listing the house file's rooms and "No room". Choosing an entry SHALL set or clear the piece's room through the owner's room route and show the new room without a reload. An API refusal SHALL be shown next to the piece it names. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: Attach an unassigned piece
- **WHEN** the owner opens the Pieces page, `murphy-bed` shows "No room", and the owner chooses `Schlafzimmer`
- **THEN** the page shows `murphy-bed` in `Schlafzimmer`, and a reload shows the same

#### Scenario: Refusal shown
- **WHEN** the room route refuses the change
- **THEN** the refusal is shown next to that piece and its room is unchanged
