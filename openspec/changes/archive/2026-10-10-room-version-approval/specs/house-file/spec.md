## ADDED Requirements

### Requirement: Deleting a composition version removes its records
When the owner deletes a composition version, the house file SHALL remove, in the same transaction, that version record. If removing the version's folder fails, the records SHALL stay as they were and the delete SHALL be reported as failed.

When the deleted version was the composition's last, the house file SHALL also remove the composition. The measured room or apartment of that scope SHALL stay.

#### Scenario: Records of the deleted version go
- **WHEN** `Wohnen` has versions 1 and 2 and the owner deletes version 1
- **THEN** the house file holds version 2 only, and measured room `Wohnen` is unchanged

#### Scenario: Last version removes the composition
- **WHEN** `Wohnen` has only version 1 and the owner deletes version 1
- **THEN** the house file holds no composition `Wohnen`, and measured room `Wohnen` is unchanged

## MODIFIED Requirements

### Requirement: Compositions are indexed and reach the turn
The house file SHALL record one composition per scope, by scope type and name. It SHALL record one version record per composition version folder, carrying what changed, the version it was revised from, and when it was approved (or nothing). A version SHALL be recorded only by a confirmed `compose_room`. A new version SHALL start unapproved. At most one version of a composition SHALL be approved at a time; approving a version SHALL clear the approval of any other version of that composition. Only the owner's approval route SHALL set or clear approval.

At the start of each turn, the Designer's and Builder's house note SHALL list the composition of the conversation's confirmed room, or of its confirmed apartment and of that apartment's rooms, with its scope, its latest version and build status, which version is approved (or that none is), and its items by name. Compositions of other rooms and apartments SHALL NOT be listed. Any placed piece version that is no longer approved SHALL be marked as such. Item names come from the owner, so they SHALL be neutralised like other owner text.

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
