## ADDED Requirements

### Requirement: Open version verdicts are in the context
When the memory settings include version verdicts (the default), a conversation's context SHALL list the bound piece's open `mismatch` verdicts, newest first and at most 5, across all of its versions. Each line SHALL name the version and carry the owner's note, neutralised so it cannot carry the untrusted-content delimiter, within the house-file block labelled as the owner's data, and labelled as the owner's verdict that the version does not match what was confirmed. Resolved and dismissed verdicts and `matches` verdicts SHALL NOT be listed. Verdicts of other pieces SHALL NOT be listed. Listing them SHALL NOT change any verdict.

#### Scenario: Designer sees the mistake
- **WHEN** `amesbury-wardrobe` v4 has an open mismatch "the side sections lost their 5 drawers" and the owner asks for a revision
- **THEN** the Designer's context lists that note, labelled version 4 and as the owner's verdict

#### Scenario: Resolved not shown
- **WHEN** v4's mismatch is resolved
- **THEN** the next turn's context lists no verdict for v4

#### Scenario: Setting off
- **WHEN** the developer turns version verdicts off in the memory settings
- **THEN** the next turn's context lists no verdicts, and the verdicts are still stored
