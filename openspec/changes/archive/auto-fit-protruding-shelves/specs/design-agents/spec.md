## ADDED Requirements

### Requirement: A fit to a protruding shelf is shown in the revision confirmation
The `revise_package` confirmation SHALL list each automatic position or envelope change from a fit to a front-protruding shelf as its own lines, after the owner's stated changes, naming each moved module or wall shelf with its old and new `y` in mm, the envelope depth old and new, and the shelf that caused it. Nothing SHALL be saved before the owner confirms. The requested-measurement check SHALL NOT require the owner to have stated the fitted lengths. The Designer's instructions SHALL say that a protruding shelf needs no separate `y` or envelope change and SHALL NOT tell the owner the module must be deepened to hold it.

#### Scenario: Confirmation shows the fit
- **WHEN** the owner asks for the second shelf to be 550 mm deep on a 400 mm cabinet
- **THEN** the confirmation lists the shelf depth, `cabinet` `y` 0 → 162 mm and the envelope depth 400 → 562 mm, and asks for "yes"

#### Scenario: Fitted lengths need no owner quote
- **WHEN** the owner stated only the shelf depth
- **THEN** the measurement check accepts the revision although `y` and the envelope depth changed by the fit

### Requirement: A side fold changes only when the owner asks for it
A revision that sets, changes or clears a module's `side_folds` SHALL be refused before any confirmation, naming `side_folds` and the module, unless the revision's `requested` list holds an entry for that module with field `side_folds` whose quote appears verbatim in the owner's own messages since the piece's last created version and names a fold or bend. A clear SHALL carry the same entry. A fold the revision does not mention SHALL be kept. The refusal SHALL tell the Designer to ask the owner rather than clear a fold to satisfy another rule, and nothing SHALL be saved. A revision that restates the fold's existing value SHALL need no entry.

#### Scenario: A fold cleared without a request
- **WHEN** the owner asked only for a 550 mm second shelf and the Designer's revision also sets `side_folds` to `[]`
- **THEN** it is refused naming `side_folds` on `cabinet`, no confirmation is shown, and no version is created

#### Scenario: A fold changed at the owner's request
- **WHEN** the owner writes "make the left bend 30°" and the revision's `requested` holds that quote for `cabinet`, field `side_folds`
- **THEN** the fold change is confirmed in the usual way

#### Scenario: A fold left alone
- **WHEN** a revision does not mention `side_folds`
- **THEN** the module's folds are unchanged and no entry is asked for
