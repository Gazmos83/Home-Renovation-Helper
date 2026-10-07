## ADDED Requirements

### Requirement: Compositions are indexed and reach the turn
The house file SHALL record one composition per scope, by scope type and name. It SHALL record one version record per composition version folder, carrying what changed and the version it was revised from. A version SHALL be recorded only by a confirmed `compose_room`.

At the start of each turn, the Designer's and Builder's house note SHALL list each composition's scope, its latest version and build status, and its items by name. Any placed piece version that is no longer approved SHALL be marked as such. Item names come from the owner, so they SHALL be neutralised like other owner text.

#### Scenario: Recorded on yes
- **WHEN** the owner confirms `Wohnen` v1
- **THEN** the house file holds composition `Wohnen` (scope room) with version 1, revised from nothing

#### Scenario: House note marks unapproved
- **WHEN** a placed version has been unapproved
- **THEN** the next Designer turn's house note lists that item marked "no longer approved"
