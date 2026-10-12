## Purpose

Defines a reversible experiment that restricts undocumented guideline content on isolated copied data and measures its effect before any change to the normal chatbot corpus.

## ADDED Requirements

### Requirement: Quarantine runs only against an isolated experiment
The experiment SHALL run on a dedicated test branch/worktree with distinct experiment and automated-test databases, copied guideline files and separate upload/render roots, port and session-cookie name. It SHALL refuse startup or a mutating experiment command when isolation cannot be established or any configured resource overlaps a protected baseline resource. Setup SHALL NOT implicitly switch, stash or discard the owner's uncommitted work. Source data export SHALL be read-only and files SHALL be independent copies.

#### Scenario: Shared database detected
- **WHEN** the experiment database or its test database is the current app database
- **THEN** startup/mutation is refused before any migration, ingestion or test cleanup

#### Scenario: Shared file root detected
- **WHEN** the experiment guideline root resolves into the protected app root through a symlink
- **THEN** startup/mutation is refused and no source file is modified

#### Scenario: Baseline not coherent
- **WHEN** the required foundation/admin baseline exists only as unresolved uncommitted changes
- **THEN** branch setup waits for a coherent baseline choice without stashing or committing unrelated work

### Requirement: Quarantine preserves data and excludes content consistently
An audit SHALL identify legacy guideline source versions and mirrored owner-note/hardware-sheet content. Undocumented or unmapped content SHALL be pending/quarantined, with its reason and affected IDs/counts recorded. Quarantine SHALL preserve copied files, metadata, content and vector rows under their retention basis while excluding their text from vector, keyword and hybrid retrieval and onward cloud exports. Original owner authorship SHALL be assessed separately from reproduced third-party content; an `owner` label alone SHALL NOT approve it.

#### Scenario: Undocumented retailer PDF
- **WHEN** the copied retailer PDF has a licence note but no documented permitted operations
- **THEN** it is quarantined, its copied rows/file stay intact, and no retrieval mode returns its text

#### Scenario: Unmapped chunk
- **WHEN** a guideline chunk cannot be linked reliably to a reviewed source version
- **THEN** it is excluded with a recorded mapping reason rather than admitted by default

#### Scenario: Quarantined text in old history
- **WHEN** a future request copy would contain quarantined text from tool history or a summary
- **THEN** that content is omitted from the outbound request and the evidence limitation is stated

### Requirement: Source release requires rights and successful re-ingestion
A quarantined source SHALL be released only for the operation scopes supported by a current documented rights decision and successful provenance-preserving re-ingestion. Failed re-ingestion SHALL leave it quarantined. Remote-use permission and technical verification SHALL stay independent from local retrieval approval. Rights revocation SHALL exclude content immediately without deleting preserved audit rows.

#### Scenario: Release succeeds
- **WHEN** rights for the exact version/operations are approved and re-ingestion succeeds
- **THEN** its eligible evidence becomes searchable with the new provenance and recorded release decision

#### Scenario: Re-ingestion fails
- **WHEN** a rights-reviewed source's extraction fails
- **THEN** it remains quarantined with the reason and no stale legacy-text release

### Requirement: Quarantine evaluation reports coverage and integrity
An evaluation SHALL compare identical baseline/quarantine queries on isolated copied data and record retrieval coverage, empty results, citation/condition completeness, unsupported verification claims and latency. It SHALL separately check ordinary design, cut-list and pricing outputs and record protected database/file integrity. Reports SHALL contain metadata/metrics rather than restricted excerpts. Completing the experiment SHALL NOT promote its policy into the default app or authorise production data changes.

#### Scenario: Source coverage falls
- **WHEN** a previously answerable guideline query loses its only eligible passage
- **THEN** the report records the lost coverage and the reply states insufficient evidence rather than inventing a rule

#### Scenario: Experiment complete
- **WHEN** the comparative report is complete
- **THEN** the branch/report is available for review and the normal app still uses its original database and policy

### Requirement: Quarantined source rules remain preliminary geometry guidance
Rules and frozen hardware inputs linked to quarantined publications SHALL retain their local numerical geometry data for reproducibility, but SHALL NOT verify structural resistance, span or anchorage. Ineligible quoted source clauses SHALL NOT be exported. The experiment SHALL list affected rules as preliminary/unverified and SHALL NOT silently remove/recalibrate them or change saved-version cut lists.

#### Scenario: Quarantined bracket source
- **WHEN** a saved version holds bracket rules from the quarantined retailer publication
- **THEN** its local bracket layout/cut list is unchanged, the source is flagged unverified, and no verified capacity or ineligible source quotation is returned
