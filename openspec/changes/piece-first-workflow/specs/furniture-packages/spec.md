## ADDED Requirements

### Requirement: The owner approves and unapproves a built version
The owner SHALL be able to approve one version of a piece and to unapprove it through owner-gated routes on that version. Approval SHALL be refused with a 409 and a stated reason when the version's build has not succeeded or when the version is not recorded in the house file (a package created only through the package routes); an unknown package or version SHALL answer 404. Approving a version SHALL clear the approval of any other version of the same piece; approving an approved version or unapproving an unapproved one SHALL succeed and change nothing. Reading a version SHALL report whether it is approved and when. No model tool SHALL approve or unapprove a version.

#### Scenario: Approve a built version
- **WHEN** the owner approves `listening-wall/v4` whose build succeeded
- **THEN** reading `listening-wall/v4` reports it approved with the time, and no other version of `listening-wall` is approved

#### Scenario: Unapprove
- **WHEN** the owner unapproves the approved `listening-wall/v4`
- **THEN** reading it reports it not approved, and no version of `listening-wall` is approved

#### Scenario: Not built yet
- **WHEN** the owner approves `listening-wall/v5` while its build is `running`
- **THEN** the request is refused with a 409 saying the version must be built first, and nothing changes

#### Scenario: Without a login
- **WHEN** the approve route is called without the owner's session
- **THEN** it answers 401 and nothing changes

### Requirement: Only an approved version is priced
Pricing a version SHALL be refused, with a stated reason that the version must be approved first on the Pieces page or the conversation's project panel, when that version is not approved; the refusal SHALL hold for the Researcher's `price_cut_list` and for the owner's pricing route (409 `not_approved`), and SHALL write no pricing record. An existing pricing record SHALL stay readable after its version is unapproved or the approval moves to another version, and reading it SHALL report that its version is no longer approved. Reviews SHALL NOT depend on approval.

#### Scenario: Unapproved version refused
- **WHEN** the Researcher prices `listening-wall/v5` and no version of `listening-wall` is approved
- **THEN** the tool answers that v5 must be approved first on the Pieces page or the project panel, and no pricing record is written

#### Scenario: Owner route refused
- **WHEN** the owner posts a pricing for the unapproved `listening-wall/v5`
- **THEN** the route answers 409 `not_approved` with the same reason, and no pricing record is written

#### Scenario: Approved version priced
- **WHEN** `listening-wall/v4` is approved and the Researcher prices it
- **THEN** a pricing record is written for v4 as before

#### Scenario: Pricing kept after unapproval
- **WHEN** `listening-wall/v4` was priced while approved and is then unapproved
- **THEN** reading that pricing returns it unchanged and reports that its version is no longer approved
