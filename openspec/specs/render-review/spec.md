# render-review Specification

## Purpose

Defines the Reviewer's check of a rendered version against its spec and brief: what evidence it is given, what it returns, how the review is recorded, and that it can change nothing else.

## Requirements

### Requirement: A review compares a version's renders and spec with the brief
`revision_review` SHALL take a package version, defaulting to the bound piece's latest, and an optional `focus`: what the owner asked to check, in their own words. It SHALL assemble the following by code:
- the version's screenshot, labelled `iso` after the inspector's Iso camera it matches;
- its straight-on views (`front.png`, `side.png`, `top.png`) when present, labelled `front`, `side` and `top` as in the Piece Inspector, each with the dimensions it shows;
- an even spread of up to four turntable frames, or else the still;
- the room still, or up to two room frames, when present;
- the spec's facts as numbers: overall size, each module's size, shelves and fronts, materials, cut-list and hardware counts;
- the piece's confirmed brief;
- any design-rule warnings for the version;
- when `focus` is given, the line "The owner asked:" followed by the focus inside the untrusted-content delimiters, neutralised, with the untrusted-content preamble in the request.

Each turntable frame SHALL be labelled `turntable` and the direction its camera looks from, relative to the piece's front (the side the inspector's Front camera faces) and as seen when facing that front: `front`, `front-right`, `right side`, `back-right`, `back`, `back-left`, `left side` or `front-left`, taken from the frame's recorded camera position (for example `turntable front-right`). A frame whose camera position is not recorded SHALL be labelled `turntable view` with its place in the spread (1 to 4). The room still SHALL be labelled `room`, and room frames `room` and `room opposite side`. Every label sent in one review SHALL be unique; no label SHALL be a frame or image number. At most 10 images SHALL be sent.

No exploded image SHALL be sent. Asked about the inspector's exploded view, the Reviewer SHALL say it has no exploded image and answer from the spec's parts and the views it was sent, naming those views.

A version with neither a screenshot nor a render SHALL be refused, saying what must exist first. The review SHALL NOT start a build or a render.

#### Scenario: Draft turntable reviewed
- **WHEN** the owner asks for a review of a version with a 12-frame draft turntable
- **THEN** the Reviewer's model call contains the screenshot, four frames spread around the turn each labelled by a direction name, the spec facts and the brief

#### Scenario: Straight-on views reviewed
- **WHEN** the owner asks for a review of a version built with the straight-on views and a 12-frame draft turntable
- **THEN** the Reviewer's model call contains the screenshot, the views labelled `front`, `side` and `top`, four frames labelled `turntable` and a direction, the spec facts and the brief

#### Scenario: Frame named by its camera direction
- **WHEN** a turntable frame's recorded camera sits in front of the piece and to the right of its centre, at 45° to the front
- **THEN** that frame is labelled `turntable front-right`

#### Scenario: Owner's question passed as focus
- **WHEN** the owner asks "is the top shelf in the side view right?" and the Reviewer calls `revision_review` with that as `focus`
- **THEN** the model call contains "The owner asked:" and the question inside the untrusted-content delimiters

#### Scenario: Focus cannot break out of its delimiters
- **WHEN** the `focus` contains the closing delimiter and "ignore the spec"
- **THEN** the delimiter is neutralised and the focus stays inside one delimited block

#### Scenario: Question about the exploded view
- **WHEN** the owner asks "is the shelf right in the exploded view?" and the version has a draft turntable
- **THEN** the Reviewer says it has no exploded image and answers from the spec's parts and the views it was sent, naming those views

#### Scenario: Nothing to look at
- **WHEN** the version has not been built
- **THEN** the review is refused saying a build or a render must exist first

### Requirement: A review returns a structured discrepancy list
The Reviewer's answer SHALL be validated into a list of items, each with an aspect (`brief`, `proportion`, `material`, `placement`, `construction`, `render`), the expectation and where it comes from (the brief, the spec or a named design rule), the observation and the view it was seen in (one of the labels sent in that review), a severity (`minor` or `major`), and an optional suggested change in words. An item naming a view that was not sent SHALL fail validation. The recorded item SHALL keep the 1-based position of that image among the renders used, so stored reviews keep their shape. The reply SHALL name the view in words ("seen in the turntable front-right view"), never an image or frame number. An item claiming a measurement SHALL quote the spec's number rather than one estimated from the image. An answer that does not validate SHALL be reported as a failed review, not shown as findings. An empty list SHALL be a valid "no discrepancies found".

#### Scenario: Missing drawer
- **WHEN** the brief asks for two drawers and the frames show one
- **THEN** the review lists a `major` `brief` item citing the brief and the view it was seen in by name

#### Scenario: View not sent
- **WHEN** the model's answer cites a view named `turntable back` and no such image was sent
- **THEN** the reply says the review could not be completed and nothing is recorded

#### Scenario: Unvalidated answer
- **WHEN** the model's answer does not fit the discrepancy schema
- **THEN** the reply says the review could not be completed and nothing is recorded

### Requirement: Reviews are recorded and their items can be closed
Each completed review SHALL be stored with its package version, the renders it used, its items and the time; the owner SHALL be able to read a version's reviews and mark an item `resolved` or `dismissed`. Opening a review SHALL NOT change any other record.

#### Scenario: Item resolved
- **WHEN** the owner marks a review item resolved
- **THEN** it no longer appears among the open items in the Designer's context

### Requirement: The Reviewer has no write tool
The Reviewer SHALL bind only `revision_review`; it SHALL NOT create or revise a piece, record a brief, render, or change the house file other than its own review record. A request to the Reviewer to make a change SHALL be answered by saying the Designer makes changes and what the owner can ask for.

#### Scenario: Owner asks the Reviewer to fix it
- **WHEN** the owner tells the Reviewer "fix the drawer"
- **THEN** the reply says the Designer can revise it and no tool other than `revision_review` is available to the Reviewer

### Requirement: Approving a taller version raises the brief's height limit
When the owner approves a version of a piece whose overall height is greater than the piece's stored brief limit for the highest the piece may be, the system SHALL raise that limit in the stored brief to the version's overall height and record the version it came from. When the version is not taller than the limit, or the brief states no limit, the brief SHALL NOT change. No other field of the brief SHALL change, and unapproving a version SHALL NOT lower the limit. A review SHALL read the brief with this limit, so it does not expect a height below one the owner has approved.

#### Scenario: A taller approved version raises the limit
- **WHEN** the stored brief says the piece may be at most 2200 mm high and the owner approves a version that is 2238 mm high
- **THEN** the brief's limit is 2238 mm, it names that version, and the next review of the piece expects at most 2238 mm

#### Scenario: A lower version leaves the limit
- **WHEN** the limit is 2200 mm and the approved version is 2100 mm high
- **THEN** the brief's limit stays 2200 mm

#### Scenario: Nothing else in the brief changes
- **WHEN** the limit is raised
- **THEN** the brief's room, purpose, style and budget are as they were

#### Scenario: No limit stated
- **WHEN** the stored brief states no height limit and a version is approved
- **THEN** the brief is unchanged

#### Scenario: Unapproving keeps the limit
- **WHEN** the approved version that raised the limit is unapproved
- **THEN** the limit stays at the raised height

### Requirement: Approving a version dismisses its items that expect an older height limit
When the owner approves a version, the system SHALL mark as dismissed each open review item of that version whose expected text states the highest the piece may be (`max_piece_height_mm`) as a figure lower than the brief's current limit. This SHALL happen on every approval, including one that raises no limit. It SHALL NOT change any other item, SHALL NOT rewrite any review or item text, and SHALL NOT touch items of other versions. Dismissed items stay stored and the owner can still read them.

#### Scenario: Items expecting the old limit are dismissed
- **WHEN** version 17 has open items expecting "max_piece_height_mm 2200.0" and the brief's limit is 2238, and the owner approves version 17
- **THEN** those items are dismissed and no longer appear among the open items

#### Scenario: Other items stay open
- **WHEN** the same version has an open item expecting doors over the bottom two shelves
- **THEN** that item stays open

#### Scenario: Approving again clears earlier items
- **WHEN** the limit was already raised to 2238 by an earlier approval and the owner approves the version again
- **THEN** its open items that expect 2200 are dismissed

#### Scenario: Other versions are untouched
- **WHEN** version 16 has open items expecting 2200 and version 17 is approved
- **THEN** version 16's items stay open
