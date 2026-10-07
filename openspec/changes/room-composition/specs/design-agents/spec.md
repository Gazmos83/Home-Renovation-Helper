## ADDED Requirements

### Requirement: The Designer composes a room
`compose_room` SHALL take a full composition: its scope (a room, or an apartment) and its list of items with their placements. It SHALL validate the composition, then pause for the owner's `yes` with a summary. The summary SHALL list each item with its size and placement, any design-rule warnings, and, when a composition already exists for that scope, the items added, moved and removed relative to its latest version. Only `yes` SHALL create the version and start its headless build. A refusal (unknown room, unapproved version, model not ready, invalid placement) SHALL be returned to the Designer without a pause, so the Designer can state it to the owner in plain words. The Designer SHALL never write or run Blender Python.

#### Scenario: Confirmed composition
- **WHEN** the owner asks to see the approved listening wall in `Wohnen` with a sofa stand-in, and answers `yes` to the summary
- **THEN** `Wohnen` v1 is created and its build is started, and the reply says so

#### Scenario: Declined
- **WHEN** the owner answers `no`
- **THEN** no version is created and nothing is built

#### Scenario: Unapproved piece
- **WHEN** the Designer proposes a piece version that is not approved
- **THEN** no confirmation is shown, and the reply names the version and says it must be approved first

### Requirement: The Builder renders a composition through the guard
`render_turntable` SHALL accept exactly one target: a piece, a shell, or a composition (its scope name and, optionally, a version, the latest by default). A composition target SHALL follow the same tier, refusal, estimate and `final` approval rules as the other targets. It SHALL refuse a composition version whose build has not succeeded, saying it must be built first. When the composition has a placed version that is no longer approved, the reply SHALL say so. A composition with a built version SHALL give the Builder something to work on, in the same way a built piece or shell does.

#### Scenario: Draft of a room
- **WHEN** the owner asks for a draft turntable of `Wohnen`
- **THEN** the run starts at tier `draft` on the latest built version, and the reply gives the estimate and where the viewer will be

#### Scenario: Two targets
- **WHEN** a call names both a piece and a composition
- **THEN** it is refused saying to name exactly one target
