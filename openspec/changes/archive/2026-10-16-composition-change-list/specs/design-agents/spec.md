## ADDED Requirements

### Requirement: The Designer confirms the change list before recomposing
When the owner asks to change a room or apartment that already has a composition version, the Designer SHALL first restate the changes it understood as a list, one line per item added, moved or removed, naming each item by its id. It SHALL then ask the owner whether anything else should change. It SHALL call `compose_room` only after the owner says the list is complete. That one call SHALL carry every change asked for since the composition's latest version. When the owner answers with a further change, the Designer SHALL add it to the list and ask again. When the owner declines the `compose_room` summary with a reason, the Designer SHALL treat the reason as one more change, restate the whole list and ask again, and SHALL NOT call `compose_room` again in that reply. A first composition of a room or apartment SHALL NOT need this step.

#### Scenario: Removal restated first
- **WHEN** `Wohnen` v7 holds `corner-couch` and the owner writes "remove the corner couch please"
- **THEN** the Designer's reply restates "corner-couch: remove", asks whether anything else should change, no confirmation is raised and no version is created

#### Scenario: Changes gathered into one call
- **WHEN** the owner then adds "and move the dining table 300 mm towards wall 1", and then says that is all
- **THEN** one `compose_room` call carries both the removal and the move, and one summary lists `corner-couch` as removed and `dining-table` as moved

#### Scenario: Decline reason becomes a change
- **WHEN** the owner answers the summary with no and the reason "keep the couch, just move it 200 mm along wall 5"
- **THEN** no version is created, and the Designer's reply restates the list with the couch moved instead of removed and asks again without raising a new confirmation in that reply

#### Scenario: First composition unchanged
- **WHEN** `Hall` has no composition and the owner asks to see it with a sofa stand-in
- **THEN** the Designer calls `compose_room` without first asking whether anything else should change, and the summary is shown as before
