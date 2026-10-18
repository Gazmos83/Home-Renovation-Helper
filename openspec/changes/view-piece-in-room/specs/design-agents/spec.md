## ADDED Requirements

### Requirement: A piece is viewed in its room after the owner places it
When the owner asks to see the bound piece in the conversation's confirmed room, its latest version has a successful build, and that version has no stored placement in that room, the Foreman SHALL give the turn to the Designer. The Designer SHALL call `ask_placement`. Its questions SHALL be written by the application, never by the model:
1. "Where would you like to place the piece? Check out the Room layout." The choices are the room's walls in order, each "Wall N (L mm)" with its length, at most eight. A room with more walls takes the wall number as a free answer.
2. "How far from the left end of that wall should the piece start? (seen facing the wall)", with the unit mm.

The set SHALL pause the turn like any question set. With the answers, the application SHALL run the room fit itself, as `room_fit` does, for that wall and that distance, converting the distance into the wall's offset; the model passes no wall or offset.
- When it fits, the placement SHALL be stored for that piece version and room. In the same turn the application SHALL hand the turn to the Builder, which SHALL start a `draft` still of the piece in the room through the render guard, and the reply gives the estimate.
- When it does not fit, the Designer SHALL say why in plain words (the wall, how much too wide, or what is in the way) and SHALL call `ask_placement` again.

When the version already has a stored placement in that room, the request SHALL go to the Builder, which renders with it. `render_turntable` SHALL take `in_room` (true or false) instead of a room document, and SHALL read the stored placement of the version for the conversation's confirmed room. Without one it SHALL refuse, saying the piece has no place in that room yet, and start nothing. A new version has no placement until one is chosen for it.

#### Scenario: First view in the room
- **WHEN** `lamellen-kommode` v1 is built, the conversation's room is `Wohnen` with five walls, no placement is stored, and the owner writes "I would like to view this in the room"
- **THEN** the Designer's question set asks "Where would you like to place the piece? Check out the Room layout." with the choices "Wall 1 (6200 mm)" to "Wall 5 (…)", and nothing renders yet

#### Scenario: Placed and shown
- **WHEN** the owner answers "Wall 2 (5700 mm)" and "300"
- **THEN** the room fit runs for wall 2 at the matching offset, the placement is stored for `lamellen-kommode` v1 in `Wohnen`, and in the same turn a `draft` still in the room starts and the reply gives the estimate

#### Scenario: Does not fit
- **WHEN** the owner answers a wall and a distance that leave the piece 150 mm past the wall's end
- **THEN** the reply says the piece is 150 mm too wide there and the placement questions are asked again; nothing is stored or rendered

#### Scenario: Shown again
- **WHEN** `lamellen-kommode` v1 has a stored placement in `Wohnen` and the owner asks to see it in the room again
- **THEN** the Builder starts a `draft` still in the room with no questions

#### Scenario: No placement, Builder call refused
- **WHEN** the Builder calls `render_turntable` with `in_room` true for a version with no stored placement in the conversation's room
- **THEN** the call is refused saying the piece has no place in that room yet, and nothing starts

#### Scenario: Room declined
- **WHEN** the conversation declined a room and the owner asks to see the piece in a room
- **THEN** the reply is "Which room is this for?"
