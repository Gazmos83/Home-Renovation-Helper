## ADDED Requirements

### Requirement: The owner approves and unapproves a built composition version
The owner SHALL be able to approve one version of a composition and to unapprove it through owner-gated routes on that version. Approval SHALL be refused with a 409 and a stated reason when the version's build has not succeeded, when the version is not recorded, or when any placed piece version is not currently approved (naming those pieces). An unknown composition or version SHALL answer 404. Approving a version SHALL clear the approval of any other version of the same composition; approving an approved version or unapproving an unapproved one SHALL succeed and change nothing. A new composition version SHALL start unapproved. Reading a composition SHALL report which version is approved, or none. No model tool SHALL approve or unapprove a composition version.

#### Scenario: Approve a built room version
- **WHEN** the owner approves `Wohnen` version 2 whose build succeeded and whose placed pieces are currently approved
- **THEN** reading `Wohnen` reports version 2 approved with the time, and no other version of `Wohnen` is approved

#### Scenario: Unapprove a room version
- **WHEN** the owner unapproves the approved `Wohnen` version 2
- **THEN** reading it reports no version of `Wohnen` approved

#### Scenario: Unapproved pieces refuse room approval
- **WHEN** `Wohnen` version 2 places `listening-wall` v4 and v4 is not approved, and the owner approves version 2
- **THEN** the request is refused with a 409 naming `listening-wall` v4, and version 2 stays unapproved

#### Scenario: Not built yet
- **WHEN** the owner approves `Wohnen` version 3 while its build is `running`
- **THEN** the request is refused with a 409 saying the version must be built first, and nothing changes

#### Scenario: Without a login
- **WHEN** the composition approve route is called without the owner's session
- **THEN** it answers 401 and nothing changes

### Requirement: A composition version can be deleted
The owner SHALL be able to delete one version of a composition. Deleting SHALL remove the version's folder with everything in it: the input, the model, the screenshot, the renders and the viewer. The service SHALL refuse the delete, without changing anything, and say why in plain words when:
- the version is approved ("unapprove version N first");
- its build or one of its renders is queued or running;
- the version does not exist.

Deleting the only remaining version of a composition SHALL delete the composition. The measured room SHALL stay. Version numbers SHALL never be reused. After a deletion, the next version of the composition SHALL be numbered one above the highest version it ever had, whether or not that version still exists. Deleting is an owner route only; no agent tool SHALL delete a composition version.

#### Scenario: Delete an older version
- **WHEN** `Wohnen` has versions 1 to 4, version 4 is approved, and the owner deletes version 2
- **THEN** `Wohnen/v2/` no longer exists, versions 1, 3 and 4 are unchanged, and version 4 stays approved

#### Scenario: Approved version refused
- **WHEN** the owner deletes `Wohnen` version 4 while it is approved
- **THEN** the delete is refused saying to unapprove version 4 first, and nothing is removed

#### Scenario: Version still building
- **WHEN** the owner deletes a composition version whose build is running
- **THEN** the delete is refused saying the version is still building

#### Scenario: Numbers are not reused
- **WHEN** `Wohnen` has versions 1 to 3, the owner deletes version 3 and then confirms a new compose
- **THEN** the new version is version 4

#### Scenario: Last version deletes the composition
- **WHEN** `Wohnen` has only version 1 and the owner deletes it
- **THEN** composition `Wohnen` is no longer listed and the measured room `Wohnen` is unchanged

## MODIFIED Requirements

### Requirement: Only approved piece versions are placed
A `piece` item SHALL be refused, naming the package and version, when that version is not approved at the time the composition is proposed. A version unapproved after it was placed SHALL stay in the composition when that composition version is not approved. Every read of the composition SHALL then report it as "no longer approved", and so SHALL the reply that starts a build or a render. It SHALL NOT be removed or replaced silently.

Unapproving a piece version that is placed in an approved composition version SHALL be refused, naming the composition and its version, until that composition version is unapproved. The piece SHALL stay approved.

#### Scenario: Unapproved version refused
- **WHEN** the owner asks to place `listening-wall` v3, which is not approved
- **THEN** the proposal is refused saying v3 is not approved and naming the approved versions, if any

#### Scenario: Unapproved after placement
- **WHEN** `listening-wall` v4 is placed in `Wohnen` v2, `Wohnen` v2 is not approved, and the owner then unapproves v4
- **THEN** `Wohnen` v2 still lists v4, marked "no longer approved", in the Studio, in the house note and in the next render's reply

#### Scenario: Unapprove refused while the room is approved
- **WHEN** `listening-wall` v4 is placed in approved `Wohnen` v2 and the owner unapproves v4
- **THEN** the request is refused naming `Wohnen` version 2, v4 stays approved, and `Wohnen` v2 is unchanged
