## MODIFIED Requirements

### Requirement: A piece is viewed in its room after the owner places it
When the owner asks to see the bound piece in the conversation's confirmed room, or says where it goes in that room, and its latest version has a successful build, the Foreman SHALL give the turn to the Designer, whether or not a placement is stored. A message that asks to hang the piece (hang, hung, wall-mounted, hängen) with no engineering term SHALL count as saying where it goes, whichever specialist the routing model chose and whether or not it read the message as a help or engineering question.

When that version has no stored placement in the room, the Designer SHALL call `ask_placement`. Its questions SHALL be written by the application, never by the model:
1. "Where would you like to place the piece? Check out the Room layout." The choices are the room's walls in order, each "Wall N (L mm)" with its length, at most eight. A room with more walls takes the wall number as a free answer.
2. "How far from the left end of that wall should the piece start? (seen facing the wall)", with the unit mm.
3. For a piece hung on the wall only: "How far below the ceiling should the top of the piece be? (0 for flush with the ceiling)", with the unit mm.

A value the owner has already stated SHALL NOT be asked again. The Designer MAY pass the wall, the distance, the wall the distance is measured from, and the ceiling gap. The application SHALL keep each passed number only when it appears in the owner's latest message, and SHALL ask only the questions whose values are missing. When every value is present, nothing SHALL be asked, and the fit SHALL run in the same turn. A distance measured from a wall SHALL be accepted only from one of the two walls next to the chosen wall: the next wall is the left end, and the previous wall is the right end, where the distance from the left end is the wall length minus the stated distance minus the piece's width. Any other wall SHALL be refused in plain words, and its question SHALL be asked.

A piece SHALL be treated as hung only when its modules are all marked as mounted on the wall, or when the owner's latest message says so (hang, hung, wall-mounted). Otherwise it is placed standing and the ceiling question is not asked, whatever the model passed.

The application SHALL run the room fit itself, as `room_fit` does, converting the distance into the wall's offset.
- When it fits, the placement SHALL be stored for that piece version and room.
- When it does not fit, the Designer SHALL say why in plain words (the wall, how much too wide, or what is in the way) and SHALL call `ask_placement` again.

Once a placement is stored, in the same turn or before, the Designer SHALL propose the room through `compose_room` with the saved place. The application SHALL build the proposal from the room's latest composition, keeping its items, and SHALL add the bound piece at its stored placement or move it there. The proposal SHALL pause for the owner's `yes` as any composition does, and a `yes` SHALL create the room version and start its headless build, after which it shows in the room inspector. When the piece version is not approved, the Designer SHALL offer to approve it with a confirmation "Approve version N of <piece>?". A `yes` SHALL approve that version as the piece inspector does, and the Designer SHALL then propose the room. A `no` SHALL leave everything unchanged.

A placement or "view in room" turn SHALL NOT start, offer or mention a render. A render SHALL be offered only when the owner asks for one. A new version has no placement until one is chosen for it.

#### Scenario: Placement stated in the owner's words
- **WHEN** `sideboard-copy` v1 is built and approved, the conversation's room is `Wohnen`, no placement is stored, and the owner writes "Please place the sideboard along wall 2 0 mm from wall 3."
- **THEN** no question set is shown, the placement is stored as wall 2 at 0 mm from its left end, and the turn pauses on the room proposal for `Wohnen` with the sideboard on wall 2; nothing renders and the reply does not mention renders

#### Scenario: Distance from the other neighbouring wall
- **WHEN** the owner writes "wall 2, 300 mm from wall 1" for a 1200 mm piece and wall 2 is 5700 mm long
- **THEN** the placement is stored at 4200 mm from the left end of wall 2

#### Scenario: Wall not next to the chosen wall
- **WHEN** the owner writes "wall 2, 300 mm from wall 4" and wall 4 does not touch wall 2
- **THEN** the reply says the distance must be measured from a wall next to wall 2, and only the distance question is asked

#### Scenario: Hung without the owner's words
- **WHEN** the model asks to place a piece hung on the wall, the owner wrote "Please place the sideboard along wall 2 0 mm from wall 3." and the piece is not marked as mounted on the wall
- **THEN** the piece is placed standing and the ceiling question is not asked

#### Scenario: Only the wall stated
- **WHEN** the owner writes "put it on wall 2"
- **THEN** only the question "How far from the left end of that wall should the piece start? (seen facing the wall)" is asked

#### Scenario: A number the owner did not write
- **WHEN** the Designer passes a distance of 500 mm and the owner's latest message has no 500
- **THEN** the distance is not used and its question is asked

#### Scenario: First view in the room
- **WHEN** `lamellen-kommode` v1 is built, the conversation's room is `Wohnen` with five walls, no placement is stored, and the owner writes "I would like to view this in the room"
- **THEN** the Designer's question set asks "Where would you like to place the piece? Check out the Room layout." with the choices "Wall 1 (6200 mm)" to "Wall 5 (…)", and nothing renders

#### Scenario: Placed and shown
- **WHEN** the owner answers "Wall 2 (5700 mm)" and "300"
- **THEN** the placement is stored for `lamellen-kommode` v1 in `Wohnen`, and in the same turn the room proposal pauses for the owner's `yes`; no Builder turn follows

#### Scenario: Does not fit
- **WHEN** the owner answers a wall and a distance that leave the piece 150 mm past the wall's end
- **THEN** the reply says the piece is 150 mm too wide there and the placement questions are asked again; nothing is stored or proposed

#### Scenario: Shown again
- **WHEN** `lamellen-kommode` v1 has a stored placement in `Wohnen` and the owner asks to see it in the room again
- **THEN** the turn goes to the Designer, which proposes the room with the piece at its stored placement, with no placement questions

#### Scenario: Version not approved
- **WHEN** `sideboard-copy` v1 has a stored placement in `Wohnen` and no approved version
- **THEN** the turn pauses on "Approve version 1 of Sideboard (copy)?"; after `yes` the version is approved and the room proposal follows; after `no` nothing changes

#### Scenario: Follow-up does not reach the Builder
- **WHEN** the placement is stored and the owner writes "This needs to go into the inspector view!"
- **THEN** the Designer answers with the room proposal, and no render is offered

#### Scenario: No placement, Builder call refused
- **WHEN** the Builder calls `render_turntable` with `in_room` true for a piece version
- **THEN** the call is refused saying renders are made of rooms, and nothing starts

#### Scenario: Asked to hang it with no wall named
- **WHEN** `sideboard-copy` v1 is built and approved with a hung placement stored in `Wohnen`, the room proposal was declined, and the owner writes "Can you hang it now?" while the routing model chooses Intake
- **THEN** the turn goes to the Designer, which proposes the room with the piece at its stored placement

#### Scenario: Saved hung height with a decimal point
- **WHEN** the stored placement holds the underside height as 1700.0 mm under a 2500 mm ceiling
- **THEN** the room proposal accepts it and lists the piece hung at 1700 mm

#### Scenario: Room declined
- **WHEN** the conversation declined a room and the owner asks to see the piece in a room
- **THEN** the reply is "Which room is this for?"

### Requirement: The Designer composes a room
`compose_room` SHALL take a full composition: its scope (a room, or an apartment) and its list of items with their placements. For a room the list SHALL be allowed to be empty, which composes the room alone. For the conversation's room it SHALL also accept `with_saved_place` instead of a list. The list is then the room's latest composition (empty when there is none), with the bound piece's version added at its stored placement, or moved there when the piece is already in it. Without a stored placement, that call is refused saying the piece has no place in the room yet. It SHALL validate the composition, then pause for the owner's `yes` with a summary. The summary SHALL list each item with its size and placement, a wall placement given as the owner numbers walls (from 1, as the room view labels them) and as its distance from the wall's left end seen facing the wall, or say that the room is composed with no items, any design-rule warnings, and, when a composition already exists for that scope, the items added, moved and removed relative to its latest version. Only `yes` SHALL create the version and start its headless build. A refusal (unknown room, unapproved version, model not ready, invalid placement, an apartment with no items) SHALL be returned to the Designer without a pause, so the Designer can state it to the owner in plain words. The Designer SHALL never write or run Blender Python.

#### Scenario: Confirmed composition
- **WHEN** the owner asks to see the approved listening wall in `Wohnen` with a sofa stand-in, and answers `yes` to the summary
- **THEN** `Wohnen` v1 is created and its build is started, and the reply says so

#### Scenario: Empty room confirmed
- **WHEN** the owner asks for a composition of `Hall` with no furniture and answers `yes` to a summary saying the room is composed with no items
- **THEN** `Hall` v1 is created with no items and its build is started, and the reply says so

#### Scenario: Last item removed
- **WHEN** `Hall` v1 holds one stand-in and the owner confirms `Hall` with no items
- **THEN** the summary lists that stand-in as removed, and on `yes` `Hall` v2 is created with no items

#### Scenario: Declined
- **WHEN** the owner answers `no`
- **THEN** no version is created and nothing is built

#### Scenario: Unapproved piece
- **WHEN** the Designer proposes a piece version that is not approved
- **THEN** no confirmation is shown, and the reply names the version and says it must be approved first

#### Scenario: Wall placement in the owner's terms
- **WHEN** a 1000 mm wide piece is proposed on the second wall of a room, whose wall is 3000 mm long, at an offset of 2000 mm from the wall's start corner
- **THEN** the summary and its table say wall 2, 0 mm from the left end, and never wall 1 or 2000 mm

#### Scenario: Composition with the saved place
- **WHEN** `Wohnen` v4 holds `listening-wall` v18, `sideboard-copy` v1 is approved with a stored placement on wall 2, and the Designer calls `compose_room` with `with_saved_place`
- **THEN** the summary lists `listening-wall` unchanged and `sideboard-copy` added on wall 2, and nothing is created before `yes`

#### Scenario: Saved place missing
- **WHEN** the Designer calls `compose_room` with `with_saved_place` and the bound version has no stored placement in the room
- **THEN** it is refused without a pause, saying the piece has no place in the room yet
