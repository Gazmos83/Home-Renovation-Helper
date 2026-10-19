## MODIFIED Requirements

### Requirement: The saved placement is in the Designer's and the Builder's context
When the bound piece's latest version has a saved placement in the conversation's confirmed room, the Designer's and the Builder's notes SHALL state it on every turn: the room, the wall as the owner numbers it, the distance from the wall's left end, and the height of the piece's underside above the floor when it is hung. The note SHALL also name the wall at each end of the piece, as the owner numbers walls, with the code-computed clear gap from that end to that wall in whole millimetres. A specialist SHALL NOT ask the owner for a placement figure the note states.

#### Scenario: Hung sideboard placement remembered
- **WHEN** sideboard-1200 version 2 is saved on wall 2 of Wohnen, 0 mm from the left end, hung at 1700 mm, and the owner later writes "Build it and show it in the room"
- **THEN** the Builder's note states wall 2, 0 mm and 1700 mm, and no specialist asks for the height again

#### Scenario: End walls named
- **WHEN** a 1000 mm wide Murphy bed is saved on wall 2 of the five-wall Wohnen (3000 mm long, left end at wall 3), 700 mm from the left end
- **THEN** the note says its left end is 700 mm from wall 3 and its right end 1300 mm from wall 1

## ADDED Requirements

### Requirement: Gap figures come from code
When the owner asks for a distance between a piece or model and a wall, another item, or the ceiling, the Designer and the Researcher SHALL take the figure from `measure_gaps` for a named composition version, or from the saved-place note for the bound piece. They SHALL NOT work out a gap themselves. `measure_gaps` SHALL be read-only, take only a version number and an item, and use the conversation's confirmed room. Naming a different room SHALL be refused.

#### Scenario: Gap in a room version
- **WHEN** the owner asks "How much space is between the Murphy bed and wall 3 in Wohnen v12?" in a conversation whose room is Wohnen
- **THEN** `measure_gaps` is called with version 12 and the bed, and the reply states its figure for wall 3 in one sentence

#### Scenario: Other room refused
- **WHEN** the conversation's room is Wohnen and the model asks `measure_gaps` for a version of Bad
- **THEN** the tool refuses and nothing is measured
