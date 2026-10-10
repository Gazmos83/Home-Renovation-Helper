## MODIFIED Requirements

### Requirement: The owner approves and unapproves a built version
The owner SHALL be able to approve one version of a piece and to unapprove it through owner-gated routes on that version. Approval SHALL be refused with a 409 and a stated reason when the version's build has not succeeded or when the version is not recorded in the house file (a package created only through the package routes); an unknown package or version SHALL answer 404. Unapproving SHALL be refused with a 409 and a stated reason naming the composition and its version when that piece version is placed in an approved composition version. Approving a version SHALL clear the approval of any other version of the same piece; approving an approved version or unapproving an unapproved one SHALL succeed and change nothing. Reading a version SHALL report whether it is approved and when. No model tool SHALL approve or unapprove a version.

#### Scenario: Approve a built version
- **WHEN** the owner approves `listening-wall/v4` whose build succeeded
- **THEN** reading `listening-wall/v4` reports it approved with the time, and no other version of `listening-wall` is approved

#### Scenario: Unapprove
- **WHEN** the owner unapproves the approved `listening-wall/v4` and no approved composition places it
- **THEN** reading it reports it not approved, and no version of `listening-wall` is approved

#### Scenario: Unapprove refused while placed in an approved room
- **WHEN** approved `Wohnen` version 2 places `listening-wall` v4 and the owner unapproves v4
- **THEN** the request is refused with a 409 naming `Wohnen` version 2, and v4 stays approved

#### Scenario: Not built yet
- **WHEN** the owner approves `listening-wall/v5` while its build is `running`
- **THEN** the request is refused with a 409 saying the version must be built first, and nothing changes

#### Scenario: Without a login
- **WHEN** the approve route is called without the owner's session
- **THEN** it answers 401 and nothing changes
