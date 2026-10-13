## MODIFIED Requirements

### Requirement: Only an approved version is priced
Pricing a version SHALL be refused, with a stated reason that the version must be approved first on the Pieces page or the conversation's Piece panel, when that version is not approved; the refusal SHALL hold for the Researcher's `price_cut_list` and for the owner's pricing route (409 `not_approved`), and SHALL write no pricing record. An existing pricing record SHALL stay readable after its version is unapproved or the approval moves to another version, and reading it SHALL report that its version is no longer approved. Reviews SHALL NOT depend on approval.

#### Scenario: Unapproved version refused
- **WHEN** the Researcher prices `listening-wall/v5` and no version of `listening-wall` is approved
- **THEN** the tool answers that v5 must be approved first on the Pieces page or the Piece panel, and no pricing record is written

#### Scenario: Owner route refused
- **WHEN** the owner posts a pricing for the unapproved `listening-wall/v5`
- **THEN** the route answers 409 `not_approved` with the same reason, and no pricing record is written

#### Scenario: Approved version priced
- **WHEN** `listening-wall/v4` is approved and the Researcher prices it
- **THEN** a pricing record is written for v4 as before

#### Scenario: Pricing kept after unapproval
- **WHEN** `listening-wall/v4` was priced while approved and is then unapproved
- **THEN** reading that pricing returns it unchanged and reports that its version is no longer approved

### Requirement: A package holds at most 15 versions
A package SHALL hold at most 15 versions at a time. Making a new version of a package that already holds 15 SHALL be refused before anything is written. The refusal SHALL say that the piece has 15 versions and that one must be deleted first on the Pieces page or the Piece panel. This SHALL apply to every way a version is made: the package route, a revision, and a rebuild. A version that was deleted SHALL NOT count toward the limit. The limit SHALL be set in one place in code.

#### Scenario: Sixteenth version refused
- **WHEN** `hall-bench` holds 15 versions and the owner submits an edited spec to the package route
- **THEN** the request is refused saying the piece has 15 versions and one must be deleted first, and no folder is written

#### Scenario: Room again after a delete
- **WHEN** `hall-bench` holds 15 versions numbered 1 to 15, the owner deletes version 3, and a revision is confirmed
- **THEN** version 16 is made and the package holds 15 versions
