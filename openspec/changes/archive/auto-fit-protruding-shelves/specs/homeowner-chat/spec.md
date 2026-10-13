## ADDED Requirements

### Requirement: A confirmed fit is recorded in the decisions note
When the owner confirms a revision that carries a fit to a protruding shelf, the app SHALL append one row to the conversation's "decisions so far" note, with the topic naming the shelf and a decision stating the overhang, the envelope depth change and that modules were moved back by it, through the same append and checks as **Add Topic Decision**. No row SHALL be written when the revision is declined, refused or fails to build, and no row SHALL be written for a revision without a fit. The row is a record: the figures in it SHALL NOT change the spec.

#### Scenario: Row after confirmation
- **WHEN** the owner confirms the 550 mm shelf revision that fitted `y` 162 mm and envelope depth 562 mm
- **THEN** the note gains a row such as "Cabinet shelf 2: 550 mm deep, 162 mm past the front; modules moved back 162 mm and envelope depth 400 → 562 mm"

#### Scenario: Declined revision leaves the note alone
- **WHEN** the owner declines the confirmation
- **THEN** the note is unchanged
