## ADDED Requirements

### Requirement: Engineering assessments remain scoped reproducible records
The house file SHALL retain owner-confirmed assessment input snapshots and immutable reports associated with the exact piece/version, and their originating conversation when present. A conversation SHALL see only assessments of its own builds, with the active build's report status/identifier/staleness and full details fetched on demand. Narrative or owner-edited summaries SHALL NOT establish numerical evidence or verification. Geometry, input, source/property, method or rights changes SHALL be checked before showing a report as current. Deleting a conversation SHALL retain piece reports without the conversation association. Deleting a piece version SHALL remove its assessment/report records through the same deletion consistency rules as that version's other records, without deleting shared source registry records.

#### Scenario: Another conversation's piece
- **WHEN** a report belongs to a piece outside the conversation's builds
- **THEN** it is absent from that conversation's house-file context

#### Scenario: Report after revision
- **WHEN** a new version changes a reported shelf's dimensions
- **THEN** the old version's report stays immutable and is not current evidence for the new version

#### Scenario: Version deletion fails
- **WHEN** moving the version folder aside or committing the record deletion fails
- **THEN** assessment/report records stay with the version and the folder is restored, as the existing deletion rules require

#### Scenario: Cleanup fails after deletion commits
- **WHEN** removing the already-hidden version folder fails after the records are deleted
- **THEN** the version and its assessment/report records are gone, as with the version's other records, and the leftover hidden folder is never listed

#### Scenario: Conversation deleted
- **WHEN** the originating conversation is deleted
- **THEN** the piece/version report remains readable to the owner, with no association to the deleted conversation
