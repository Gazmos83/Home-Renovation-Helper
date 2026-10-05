> Copied unchanged from the predecessor repo (`Interior_Design_App/backend/fixtures/packages/`). The render and blueprint paths below refer to that repo.

# Apartment 4 living room — fixture provenance

`room-scene-apt4-living.json` is the checked-in reference room scene for Tier 2 day 5,
traced from the client's real floor plan rather than invented. This file records where its
numbers came from, so an operator can tell measured data from an assumption before a render
is used in a client-facing quote.

## Source

Blueprint: `renders/Sarah_Living_Room_ChatGPT-19-09-2026/Sarah_Fhein_Blueprints.jpeg` — apartment 4,
room "Wohnen", printed floor area **F = 32.287 m²**.

An earlier operator Blender session (`renders/Sarah_Living_Room_ChatGPT-19-09-2026/files/`,
`01_shell.py` and its `README.md`) already traced the plan by hand. This fixture's `room.corners`,
wall thickness and openings are taken directly from that trace, re-expressed in this contract's
wall-index/offset form (wall *i* runs from `corners[i]` to `corners[i+1]`, offsets measured from
each wall's own first corner):

| Item | Value | Wall (this fixture) |
|---|---|---|
| Corners (mm, SW origin, +X east, +Y north) | (0,0), (6327,0), (6325,5327), (1579,6189) | — |
| Wall thickness | 380 mm (ink band width on the plan) | all |
| Hallway door (to Flur 2) | 950 mm wide, 2050 mm tall, 3875 mm from the wall's south-west corner | wall 0 (south) |
| Terrace door | 1050 mm wide, 2200 mm tall, 149 mm from the wall's north-east corner | wall 2 (north) |
| Window | 1140 mm wide, 1300 mm tall, sill 900 mm, 2344 mm from the wall's north-east corner | wall 2 (north) |

## Scale and cross-check

The original trace's scale came from the plan's printed 5.59 m dimension chain (measured at 201 px,
≈ 27.8 mm/px). Its own cross-check: the traced polygon's shoelace area is 32.22 m², against the
plan's printed 32.287 m² — a 0.2% difference, which is the evidence that the trace is correct rather
than an independent measurement. Individual wall lengths and opening offsets may still be off by a
few centimetres; before a quote is sent, an operator should confirm the dimensions this fixture
implies against the actual site.

## Placement and furnishings

The Listening Wall (2112 × 1508 × 372 mm, the day-3 default) is centred on wall 1 (the east party
wall to apartment 3, 5327 mm long) at offset 1608 mm, matching the reference layout renders in
`renders/Sarah_Living_Room_ChatGPT-19-09-2026/` (`layout_overview.png`, `render_preview.png`,
`sofa_valencia.png`, `bookshelf.png`): the sofa faces the entertainment wall, a round coffee table
sits in front of it on a rug, a side table and lamp stand at the sofa's end, a dining table for four
sits near the terrace door, and a floor lamp stands near the window.

These furnishings are re-derived directly against the traced polygon and this contract's validator,
not copied from the reference session's own `02_furniture.py`: that script still positions
everything against an earlier, un-traced 5.80 × 5.55 m rectangle (its own `README.md` warns of this),
so its literal coordinates would not fit the real room. Round or irregular pieces (the coffee table,
the lamps) are represented as their bounding box, per this contract's box-only furnishing shape;
`build_room_scene.py` renders them as plain boxes, not as their true silhouette.

## Known assumption

**Ceiling height (2600 mm) is not on the plan.** It is carried over from the operator trace's own
assumption and must be confirmed with the client (or on site) before it is used in a client-facing
render or quote.
