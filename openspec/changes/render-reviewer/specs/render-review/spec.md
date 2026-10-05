## Purpose

Defines the Reviewer's check of a rendered version against its spec and brief: what evidence it is given, what it returns, how the review is recorded, and that it can change nothing else.

## ADDED Requirements

### Requirement: A review compares a version's renders and spec with the brief
`revision_review` SHALL take a package version (the bound piece's latest when not given) and assemble, by code, the version's screenshot, an even spread of up to four turntable frames or the still, the room still or up to two room frames when present, the spec's facts as numbers (overall size, each module's size, shelves and fronts, materials, cut-list and hardware counts), the piece's confirmed brief, and any design-rule warnings for the version. A version with neither a screenshot nor a render SHALL be refused, saying what must exist first. The review SHALL NOT start a build or a render.

#### Scenario: Draft turntable reviewed
- **WHEN** the owner asks for a review of a version with a 12-frame draft turntable
- **THEN** the Reviewer's model call contains the screenshot, four frames spread around the turn, the spec facts and the brief

#### Scenario: Nothing to look at
- **WHEN** the version has not been built
- **THEN** the review is refused saying a build or a render must exist first

### Requirement: A review returns a structured discrepancy list
The Reviewer's answer SHALL be validated into a list of items, each with an aspect (`brief`, `proportion`, `material`, `placement`, `construction`, `render`), the expectation and where it comes from (the brief, the spec or a named design rule), the observation and the image it was seen in, a severity (`minor` or `major`), and an optional suggested change in words. An item claiming a measurement SHALL quote the spec's number rather than one estimated from the image. An answer that does not validate SHALL be reported as a failed review, not shown as findings. An empty list SHALL be a valid "no discrepancies found".

#### Scenario: Missing drawer
- **WHEN** the brief asks for two drawers and the frames show one
- **THEN** the review lists a `major` `brief` item citing the brief and the frame it was seen in

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
