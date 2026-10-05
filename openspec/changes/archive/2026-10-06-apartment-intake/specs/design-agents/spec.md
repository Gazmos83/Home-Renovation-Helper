## ADDED Requirements

### Requirement: Intake reads attached plans and photos
When a turn attaches a blueprint or photo, Intake SHALL read from it only what it can see — the scale (from a dimension line, a printed area or a known door width), the room outlines, ceiling height when written, openings with their walls and offsets — and SHALL say which figures were read and which are assumed defaults, asking for any it cannot read. Intake SHALL use `record_plan` for an apartment of several rooms and `record_brief` for a single room; a photo SHALL inform materials, light and position, never a dimension the plan contradicts.

#### Scenario: Blueprint without a ceiling height
- **WHEN** the owner attaches a blueprint that shows no ceiling height
- **THEN** Intake proposes no plan until the owner gives the height, or states the 2500 mm default it would use and asks the owner to confirm it

#### Scenario: Photo contradicts the plan
- **WHEN** a photo suggests a wider window than the plan shows
- **THEN** Intake keeps the plan's width and mentions the difference to the owner
