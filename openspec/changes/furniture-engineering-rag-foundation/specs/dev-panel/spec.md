## ADDED Requirements

### Requirement: Developer manages engineering source rights and verification
Behind the developer gate, the developer SHALL list/register engineering metadata and files, inspect current rights decisions, approve/revoke documented operation scopes, review technical verification, ingest/re-ingest approved content and inspect failures/metadata-only reasons. Rights and technical verification SHALL be displayed separately. Engineering upload/registration SHALL NOT index immediately on a licence note. A locally supplied large document SHALL have a confined ingestion path even when it exceeds the browser upload cap, without silently changing that cap.

#### Scenario: Engineering source registered pending
- **WHEN** a developer registers a manufacturer manual without rights evidence
- **THEN** the page shows pending/link-only with no searchable excerpt

#### Scenario: Panel disabled
- **WHEN** the developer panel is disabled and an engineering administration route is requested with a valid session
- **THEN** the response is 404

#### Scenario: No session
- **WHEN** an engineering source approval route is requested without the owner session
- **THEN** the response is 401 and no approval is recorded

### Requirement: Developer manages typed numerical evidence without automatic verification
The developer SHALL create/review numerical records with product identity, canonical/original units, value basis, range/conditions and source/page. Invalid units, missing provenance for a supplied value or product mismatches SHALL be refused naming the field. Candidate values SHALL stay unverified until explicit technical review. No shipped material/anchor capacity SHALL be invented to make the catalogue appear complete.

#### Scenario: Property lacks provenance
- **WHEN** a developer supplies an elasticity value with no source revision/page
- **THEN** the save is refused naming provenance and the verified property remains unchanged

#### Scenario: Candidate saved
- **WHEN** an extracted value is saved as a review candidate
- **THEN** it is labelled unverified and cannot satisfy a verified engineering input
