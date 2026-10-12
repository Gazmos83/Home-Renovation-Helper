## MODIFIED Requirements

### Requirement: Guideline publications are ingested from a checked-in source list
The guideline corpus SHALL be built from a checked-in source list naming each publication with its title, jurisdiction, version or date, licence note and either a file the owner placed under the guidelines folder (`docs/guidelines/`; PDF or Markdown) or an official URL. A file source SHALL be read locally, with no network request, and SHALL be refused when its path leaves the guidelines folder or the file is missing. A URL source SHALL be fetched under the same robots and identity rules as retail pages. Outside the isolated quarantine experiment, PDF, HTML and Markdown text SHALL be extracted, chunked by section where the text marks sections, and embedded into the corpus under the category `guideline` as before. A source that refuses, cannot be read or is missing SHALL be reported and skipped, never fetched another way. A publication whose host refuses this service SHALL NOT be listed by URL; the owner supplies it as a file. Outside the experiment, DIN standards and copyrighted guides SHALL remain local owner files and SHALL NOT be committed to the repository.

Inside the isolated quarantine experiment, extraction, embedding and content retrieval SHALL additionally require documented rights for the exact source version and relevant operations. Local possession SHALL NOT satisfy this gate. A source without approval SHALL remain metadata-only/quarantined, with a reason; existing copied chunks/files SHALL be preserved. The experiment SHALL NOT change the default app's ingestion policy or data. Engineering use SHALL always obey the foundation eligibility rules, regardless of experiment mode.

#### Scenario: Local PDF ingested
- **WHEN** outside the experiment the owner places the ASR A1.2 PDF under the guidelines folder, lists it, and runs the guideline ingestion
- **THEN** its passages are searchable with their rule number, section and publication date, and no network request was made

#### Scenario: Missing file
- **WHEN** a listed file does not exist
- **THEN** the ingestion reports it by source id, skips it and continues with the others

#### Scenario: Path outside the folder
- **WHEN** a listed path leaves the guidelines folder
- **THEN** loading the source list fails naming the source

#### Scenario: Experiment source has no rights approval
- **WHEN** the experiment ingester encounters a local PDF with only a licence note
- **THEN** it reports pending rights review and performs no new text extraction or embedding

## ADDED Requirements

### Requirement: Experiment rights gate also controls guideline mirrors and uploads
Inside the isolated quarantine experiment, the rights gate SHALL override immediate indexing/retrieval of uploaded PDFs and mirrored owner notes/hardware sheets. Creating/editing a local record SHALL preserve its ordinary field validation, but reproduction, extraction and corpus mirroring SHALL wait for permitted source/version rights. Unapproved uploads SHALL be byte-checked/staged only when retention is authorised, listed as pending and not parsed for readability or ingested. Outside the experiment these legacy behaviours SHALL remain as before; engineering use SHALL still require foundation eligibility.

#### Scenario: Upload pending review
- **WHEN** an experiment developer uploads a PDF with title/date/licence note but no approved extraction rights
- **THEN** it is listed as pending rather than searchable and no readability text extraction has run

#### Scenario: Note reproduces a book table
- **WHEN** a copied owner note reproduces third-party content without documented processing rights
- **THEN** its corpus mirror is quarantined despite its owner label and source citation

#### Scenario: Hardware sheet mirror
- **WHEN** a hardware sheet has valid drilling fields but no reviewed rights for its mirrored source text
- **THEN** the experiment keeps the local fields while excluding the text mirror from corpus/model use

#### Scenario: Existing validation retained
- **WHEN** an experiment upload is not a PDF by its bytes or leaves a confined path
- **THEN** it is refused by the existing file validation rather than staged as a pending source
