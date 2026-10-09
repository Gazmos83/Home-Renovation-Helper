## ADDED Requirements

### Requirement: A stored room enters a conversation only through a confirmation
A room or apartment held by the house file SHALL become part of a conversation only through a confirmation that shows its stored measurements: `confirm_room`, a `record_brief` naming it, or a `record_plan` for its apartment. This holds whichever conversation first stored it, and even after that conversation has been deleted. No room's measurements SHALL be used in a turn's numbers, a piece's placement or a composition before the conversation has confirmed it. Deleting a conversation SHALL keep the rooms and apartments it stored.

When `record_brief` corrects a room that belongs to an apartment, the room SHALL stay in that apartment.

#### Scenario: Same blueprint in a new conversation
- **WHEN** apartment `Wohnung` with `Wohnen` and `Küche` was stored in a conversation that the owner has since deleted, and in a new conversation the owner attaches the same blueprint
- **THEN** no room is confirmed and no stored figure is used until the owner answers `yes` to a card that shows `Wohnung`'s stored rooms

#### Scenario: Stored room offered, not assumed
- **WHEN** `Hall` is stored, a new conversation has no confirmed room, and the owner writes "a shoe bench for the hall"
- **THEN** the hall's stored size, ceiling height and openings are shown on a card before any number is proposed, and nothing uses them before `yes`

#### Scenario: Apartment room corrected through a brief
- **WHEN** `Küche` belongs to `Wohnung` and the owner confirms a `record_brief` that corrects the kitchen's ceiling height
- **THEN** `Küche` has the new height and still belongs to `Wohnung`
