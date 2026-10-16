## ADDED Requirements

### Requirement: The hinge count per door follows the data sheet, then the hinge-count rule
The hinge calculation SHALL count each door's hinges from, in this order:
1. the count table on the hinge item's data sheet, when the sheet has one;
2. otherwise, the hinge-count rule in the version's frozen inputs;
3. otherwise, the built-in fallback: 2 hinges up to 900 mm, 3 up to 1600 mm, 4 above.

The hinge positions, the plate positions and the hinge cup borings SHALL all use that same count. The count's source SHALL be listed with the hinge entry: the data sheet, the rule's id and its quoted source, or the fallback. The rule SHALL be read only from the frozen inputs, so an existing version's drilling list SHALL NOT change when the rules are edited later. The shelf-pin hole calculation SHALL be unchanged by the pin-count rule: its holes still need the pin item's data sheet.

#### Scenario: Rule decides a 1000 mm door
- **WHEN** a version has two 1000 mm doors, its frozen inputs hold the `hinge-count` rule, and its hinge has no data sheet
- **THEN** the drilling list counts 2 hinges per door and 4 hinge cup borings, and names `hinge-count` and its owner note as the count's source

#### Scenario: Data sheet table wins over the rule
- **WHEN** a hinge's data sheet gives a count table with 3 hinges up to 1100 mm, and a 1000 mm door uses it under the `hinge-count` rule
- **THEN** the door gets 3 hinges, and the source named is the data sheet

#### Scenario: Version without the rule keeps the fallback
- **WHEN** a version's frozen inputs hold no hinge-count rule, and it has a 1000 mm door
- **THEN** the door gets 3 hinges, as before this change

#### Scenario: Frozen rule kept after an edit
- **WHEN** the developer edits `hinge-count` after `hall-cabinet` version 2 was built
- **THEN** version 2's drilling list and hardware are unchanged, and the next version built uses the edited rule
