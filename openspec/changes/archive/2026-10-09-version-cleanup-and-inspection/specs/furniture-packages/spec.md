## ADDED Requirements

### Requirement: A package version can be deleted
The owner SHALL be able to delete one version of a package. Deleting SHALL remove the version's folder with everything in it: the input, the model, the screenshot and views, the renders, the cut list and the drilling list. The service SHALL refuse the delete, without changing anything, and say why in plain words when:
- the version is approved ("unapprove version N first");
- a room composition version places it (naming the composition and its version);
- its build or one of its renders is queued or running;
- the version does not exist.

Deleting the only remaining version of a package SHALL delete the package. Version numbers SHALL never be reused. After a deletion, the next version of the package SHALL be numbered one above the highest version it ever had, whether or not that version still exists. Deleting is an owner route only; no agent tool SHALL delete a version.

#### Scenario: Delete an older version
- **WHEN** `hall-bench` has versions 1 to 4, version 4 is approved, and the owner deletes version 2
- **THEN** `hall-bench/v2/` no longer exists, versions 1, 3 and 4 are unchanged, and version 4 stays approved

#### Scenario: Approved version refused
- **WHEN** the owner deletes `hall-bench` version 4 while it is approved
- **THEN** the delete is refused saying to unapprove version 4 first, and nothing is removed

#### Scenario: Version placed in a composition
- **WHEN** composition `Living room` version 3 places `hall-bench` version 2 and the owner deletes `hall-bench` version 2
- **THEN** the delete is refused naming `Living room` version 3, and nothing is removed

#### Scenario: Version still building
- **WHEN** the owner deletes a version whose build is running
- **THEN** the delete is refused saying the version is still building

#### Scenario: Numbers are not reused
- **WHEN** `hall-bench` has versions 1 to 5, the owner deletes version 5 and then a revision is confirmed
- **THEN** the new version is version 6

#### Scenario: Last version deletes the package
- **WHEN** `hall-bench` has only version 1 and the owner deletes it
- **THEN** the `hall-bench` folder no longer exists and the package is no longer listed

### Requirement: A package holds at most 15 versions
A package SHALL hold at most 15 versions at a time. Making a new version of a package that already holds 15 SHALL be refused before anything is written. The refusal SHALL say that the piece has 15 versions and that one must be deleted first on the Pieces page or the Project panel. This SHALL apply to every way a version is made: the package route, a revision, and a rebuild. A version that was deleted SHALL NOT count toward the limit. The limit SHALL be set in one place in code.

#### Scenario: Sixteenth version refused
- **WHEN** `hall-bench` holds 15 versions and the owner submits an edited spec to the package route
- **THEN** the request is refused saying the piece has 15 versions and one must be deleted first, and no folder is written

#### Scenario: Room again after a delete
- **WHEN** `hall-bench` holds 15 versions numbered 1 to 15, the owner deletes version 3, and a revision is confirmed
- **THEN** version 16 is made and the package holds 15 versions
