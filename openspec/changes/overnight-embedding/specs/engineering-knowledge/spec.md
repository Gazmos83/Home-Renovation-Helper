## ADDED Requirements

### Requirement: Interrupted ingestion resumes without bypassing publication rules
Ingestion SHALL save each completed batch of locally computed vectors, keyed by version and passage content hash, before embedding the next batch. A later run for the same version SHALL reuse saved vectors whose content hash still matches and SHALL embed only the remaining passages. Saved vectors SHALL NOT be searchable, retrievable or sent to any model before publication. Publication SHALL remain atomic and SHALL recheck current rights for every block. Saved vectors for a version SHALL be deleted once that version is published, and when the version loses its embedding or retention rights.

#### Scenario: Run interrupted midway
- **WHEN** an ingestion run stops after 800 of 2,391 passages are embedded and is started again
- **THEN** the new run embeds only the remaining 1,591 passages, and the previously published blocks stay searchable until the new set is published

#### Scenario: Staged vectors are not evidence
- **WHEN** a search runs while a version has saved but unpublished vectors
- **THEN** no result comes from those saved vectors

#### Scenario: Rights withdrawn while staged
- **WHEN** embedding or retention rights are withdrawn for a version with saved vectors
- **THEN** its saved vectors are deleted, and a later run refuses to start and names the missing right

#### Scenario: Extraction changed between runs
- **WHEN** a passage's text differs from the text whose vector was saved
- **THEN** that passage is embedded again, and the saved vector for the old text is not used
