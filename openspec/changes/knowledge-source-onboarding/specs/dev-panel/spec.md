## ADDED Requirements

### Requirement: Source onboarding is prefilled but every decision is explicit
The developer Knowledge page SHALL list catalogue entries not yet registered and register one only when the developer presses Register, as metadata only and unverified. The rights form SHALL offer prefilled reviewer, an editable draft evidence note and named grant presets that list their exact operations; no preset SHALL be preselected. A rights decision, a revocation and a technical review SHALL be recorded only by an explicit click on that decision, never as a side effect of registration, ingestion, a preset or a catalogue field. A catalogue or drafted value SHALL NOT set `approved_for_embedding`, a verification status or a reviewer.

#### Scenario: Catalogue entry registered
- **WHEN** the developer registers an unregistered catalogue entry
- **THEN** a metadata-only unverified version exists, with no rights, content, verification or reviewer recorded

#### Scenario: Preset chosen but not confirmed
- **WHEN** the developer selects a grant preset and does not press Record approval
- **THEN** no rights decision is stored and no operation is permitted

#### Scenario: Preset confirmed
- **WHEN** the developer edits the evidence note and presses Record approval with the "Local use" preset
- **THEN** one append-only decision grants only extraction, local embedding, local retrieval and retention, with the stated reviewer and evidence

#### Scenario: Catalogue claims verification
- **WHEN** a catalogue entry carries a verified status or an embedding approval
- **THEN** registration refuses it and nothing is stored as verified or approved

### Requirement: Official-link ingestion is rights-gated and bounded
Ingest from official link SHALL run only for a version with an HTTPS `source_url` and current extraction, retention and embedding rights, through the existing pinned-address fetcher without redirects. It SHALL refuse a host whose robots rules deny the service, a response above its size cap or a changed content hash, and SHALL report the refusal reason. The raised cap SHALL apply to this action only and SHALL NOT change browser upload limits.

#### Scenario: Rights missing
- **WHEN** the developer ingests from the official link without current extraction rights
- **THEN** nothing is fetched or published and the missing right is named

#### Scenario: Document changed
- **WHEN** the remote document's hash differs from the stored hash
- **THEN** ingestion is refused and a new source version is required

#### Scenario: Document too large
- **WHEN** the response exceeds the configured cap
- **THEN** ingestion stops with a stated limit and no partial content is stored
