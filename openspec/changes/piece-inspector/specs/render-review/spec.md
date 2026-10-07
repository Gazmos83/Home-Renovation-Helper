## MODIFIED Requirements

### Requirement: A review compares a version's renders and spec with the brief
`revision_review` SHALL take a package version, defaulting to the bound piece's latest. It SHALL assemble the following by code:
- the version's screenshot;
- its straight-on views (`front.png`, `side.png`, `top.png`) when present, each labelled with the view and the dimensions it shows;
- an even spread of up to four turntable frames, or else the still;
- the room still, or up to two room frames, when present;
- the spec's facts as numbers: overall size, each module's size, shelves and fronts, materials, cut-list and hardware counts;
- the piece's confirmed brief;
- any design-rule warnings for the version.

A version with neither a screenshot nor a render SHALL be refused, saying what must exist first. The review SHALL NOT start a build or a render.

#### Scenario: Draft turntable reviewed
- **WHEN** the owner asks for a review of a version with a 12-frame draft turntable
- **THEN** the Reviewer's model call contains the screenshot, four frames spread around the turn, the spec facts and the brief

#### Scenario: Straight-on views reviewed
- **WHEN** the owner asks for a review of a version built with the straight-on views and a 12-frame draft turntable
- **THEN** the Reviewer's model call contains the screenshot, the front, side and top views labelled by view, four frames, the spec facts and the brief

#### Scenario: Nothing to look at
- **WHEN** the version has not been built
- **THEN** the review is refused saying a build or a render must exist first
