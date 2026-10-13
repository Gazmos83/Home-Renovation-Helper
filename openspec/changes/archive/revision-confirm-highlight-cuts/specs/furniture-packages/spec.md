## REMOVED Requirements

### Requirement: A revision preview lists hardware and cut-list changes
**Reason**: The confirmation card listed every derived cut-list and hardware line, which buried the owner's change lines. Those details belong in the inspector after the build, with new and changed rows highlighted.
**Migration**: Confirmations show only change lines (plus existing warnings, version-limit heads-up and auto-fit lines). Inspect the built version's Cut list tab for added and changed parts and hardware.

## ADDED Requirements

### Requirement: A revision confirmation lists change lines only
The confirmation `revise_package` shows SHALL list the change lines for the revision (what the owner asked to change on the document), and SHALL NOT list derived cut-list rows or hardware quantity lines. Design-rule warnings, the version-limit heads-up when the new version would be the 13th, 14th or 15th, and any auto-fit lines the revision already adds SHALL still appear when they apply. The cut list and hardware of the resulting version SHALL remain readable in the inspector after the build.

#### Scenario: Change lines only
- **WHEN** the Designer proposes adding a divider on `cabinet`
- **THEN** the confirmation lists the divider change line and does not list `Cut list:` or `Hardware:` lines

#### Scenario: Fixing a shelf still shows the change lines
- **WHEN** the owner agrees to fix the top of four adjustable shelves and the Designer proposes the revision
- **THEN** the confirmation lists the shelf-kind and count change lines and does not list confirmat or shelf-pin quantity lines

#### Scenario: Warnings and heads-up remain
- **WHEN** a revision that would create version 13 also breaches a warn-level design rule
- **THEN** the confirmation still includes the design-rule warning and the version-limit heads-up after the change lines
