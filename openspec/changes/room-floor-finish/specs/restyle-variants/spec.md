## MODIFIED Requirements

### Requirement: A style applies to a composition's surfaces
A room restyle request SHALL name a style preset and a composition version, which is rebuilt in memory from its stored document. The style SHALL change the walls, ceiling and floor, the world light, and the colour of each stand-in (by the colour map, else the fallback tint) as listed in that version's surface map. When the version carries a floor finish, the floor SHALL keep that finish and the style SHALL NOT change it. Placed pieces and library models SHALL keep their own appearance. The composition's items, sizes and placements SHALL NOT change.

#### Scenario: Room restyled
- **WHEN** the style `japandi` is applied to `Wohnen` v3 that holds one approved piece, one stand-in `sofa` and one library model
- **THEN** the walls, floor, ceiling and light follow the style, the sofa takes its mapped colour, and the piece and the library model look as built

#### Scenario: Composition not built
- **WHEN** a restyle is requested for a composition version whose build has not succeeded
- **THEN** it is refused stating the build has not succeeded, and nothing is rendered

#### Scenario: Tiled floor kept
- **WHEN** the style `japandi` is applied to `Wohnen` v5, whose document carries a floor finish of 600 × 600 mm tiles
- **THEN** the walls, ceiling and light follow the style, and the floor keeps its tiles and colours

