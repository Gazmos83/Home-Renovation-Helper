## MODIFIED Requirements

### Requirement: Compositions are indexed and reach the turn
The house file SHALL record one composition per scope, by scope type and name. It SHALL record one version record per composition version folder, carrying what changed, the version it was revised from, and when it was approved (or nothing). A version SHALL be recorded only by a confirmed `compose_room`. A new version SHALL start unapproved. At most one version of a composition SHALL be approved at a time; approving a version SHALL clear the approval of any other version of that composition. Only the owner's approval route SHALL set or clear approval.

At the start of each turn, the house note of the Foreman, Intake, the Designer and the Builder SHALL list the composition of the conversation's confirmed room, or of its confirmed apartment and of that apartment's rooms, with its scope, its latest version and build status, and which version is approved (or that none is). When a version is approved, the note SHALL list that version's items: each placed piece by package id and version, each library model by name and stated size, each stand-in by name, with where each one stands. When a later version than the approved one exists, its items SHALL be listed separately, labelled as a draft that is not approved. When no version is approved, the latest version's items SHALL be listed, labelled as not approved. A conversation with no confirmed room or apartment SHALL see no composition. Compositions of other rooms and apartments SHALL NOT be listed. Any placed piece version that is no longer approved SHALL be marked as such. Item names come from the owner, so they SHALL be neutralised like other owner text.

#### Scenario: Recorded on yes
- **WHEN** the owner confirms `Wohnen` v1
- **THEN** the house file holds composition `Wohnen` (scope room) with version 1, revised from nothing, unapproved

#### Scenario: House note marks unapproved
- **WHEN** a placed version in the conversation's room has been unapproved
- **THEN** the next Designer turn's house note lists that item marked "no longer approved"

#### Scenario: Other room's composition left out
- **WHEN** the conversation's confirmed room is `Hall` and a composition exists for `Wohnen`
- **THEN** the Designer's house note does not list `Wohnen`

#### Scenario: Approving another version moves the approval
- **WHEN** `Wohnen` version 2 is approved and the owner approves version 3
- **THEN** version 3 is approved and version 2 is not

#### Scenario: A new piece conversation sees the approved layout
- **WHEN** `Wohnen` version 2 is approved and places the piece `lamellen-kommode` v3 and the library model "Sofa Lund" (2200 × 950 × 850 mm), and a new conversation confirms `Wohnen`
- **THEN** Intake's first turn in that conversation carries both items with their places, labelled as approved version 2

#### Scenario: A newer draft does not hide the approved layout
- **WHEN** `Wohnen` version 2 is approved and version 3, not approved, removes the sofa
- **THEN** the note lists version 2's items, sofa included, and lists version 3's items separately as a draft that is not approved

#### Scenario: No room, no composition
- **WHEN** a conversation has no confirmed room and `Wohnen` has an approved composition
- **THEN** no agent's house note in that conversation lists `Wohnen`'s items
