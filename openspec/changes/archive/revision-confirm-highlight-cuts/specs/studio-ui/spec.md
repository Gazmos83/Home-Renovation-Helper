## ADDED Requirements

### Requirement: The Cut list tab highlights new and changed rows in red
When the inspector shows a built version that was revised from another version, the Cut list tab SHALL highlight in red every cut-list row that is new or whose length, width, thickness or quantity differs from that row on the revised-from version, and every hardware line that is new or whose quantity differs. Unchanged rows SHALL keep normal styling. Removed rows from the earlier version SHALL NOT appear. Version 1, a version with no revised-from, and a version whose revised-from has no readable `spec.json` SHALL show every row in normal styling. The highlight SHALL appear in both the inspector page and the conversation's split view. The page SHALL pass a recorded browser check before it counts as done.

#### Scenario: New divider row is red
- **WHEN** the owner opens the Cut list of a version revised from the previous one by adding a divider
- **THEN** the new divider part row is shown in red and the unchanged carcass rows are not

#### Scenario: Changed hardware quantity is red
- **WHEN** the owner opens the Cut list of a version whose confirmat quantity rose against the revised-from version
- **THEN** that hardware row is shown in red and hardware lines whose quantity is unchanged are not

#### Scenario: Version 1 has no red rows
- **WHEN** the owner opens the Cut list of version 1
- **THEN** every part and hardware row uses normal styling
