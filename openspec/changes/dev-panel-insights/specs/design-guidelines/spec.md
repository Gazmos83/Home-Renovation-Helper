## ADDED Requirements

### Requirement: Guideline PDFs can be uploaded from the developer panel
The developer SHALL be able to upload a guideline PDF with a title, jurisdiction, publication date and licence note. The upload SHALL be refused, naming the problem, when the file is not a PDF (by its content, not its name), is larger than the upload cap, cannot be read as text, or has the same content as a source already listed. An accepted file SHALL be stored under the gitignored guidelines PDF folder with a generated file name, recorded with its metadata, and ingested into the corpus at once under the category `guideline`, with no network request. The developer SHALL be able to list every guideline source (checked-in and uploaded) with its ingestion state, re-ingest one, and delete an uploaded one, which removes its file and its passages. Checked-in sources SHALL NOT be deletable from the panel. Ingestion from the command line SHALL include uploaded sources. Uploaded passages SHALL carry the same prompt-injection delimiters as every other retrieved chunk. The routes SHALL sit behind the developer gate.

#### Scenario: PDF uploaded and searchable
- **WHEN** the developer uploads a readable PDF titled "ASR A1.2" with its date and licence note
- **THEN** it is listed as ingested, and `search_guidelines` can return its passages with that title and date

#### Scenario: Not a PDF
- **WHEN** the uploaded file is a renamed image
- **THEN** it is refused as not a PDF and nothing is stored

#### Scenario: Same file twice
- **WHEN** the developer uploads a file whose content matches an uploaded source
- **THEN** it is refused naming the existing source

#### Scenario: Upload deleted
- **WHEN** the developer deletes an uploaded source
- **THEN** its file and its passages are gone, and `search_guidelines` no longer returns them

#### Scenario: Checked-in source protected
- **WHEN** the developer tries to delete a source from the checked-in list
- **THEN** it is refused, and the source stays

#### Scenario: Panel disabled
- **WHEN** the panel is disabled and an upload route is called with a valid session
- **THEN** the response is 404

### Requirement: Design rules are edited from the developer panel
The developer SHALL be able to list every design rule with its id, check, parameters, severity, quoted source and origin (the checked-in table or the panel), and to add a rule or edit one. A rule SHALL name a check from the closed set and SHALL cite a source: a listed publication or an existing owner note. A saved rule SHALL be validated exactly as the checked-in table is at startup; a rule that fails SHALL be refused naming the rule and the field, and the rules in force SHALL stay unchanged. A saved rule SHALL apply from the next check, without a restart. Edits SHALL be stored apart from the checked-in table, which SHALL NOT be rewritten. Resetting an edited rule SHALL restore the checked-in version; a rule added on the panel SHALL be deletable. A stored edit that no longer validates at startup SHALL be skipped and shown as invalid, naming the rule, and SHALL NOT stop the service. The routes SHALL sit behind the developer gate.

#### Scenario: Rule added from the panel
- **WHEN** the developer adds a `shelf_span_mm_for_thickness` rule of 800 mm for 18 mm boards citing an owner note
- **THEN** the next piece check measures shelf spans against 800 mm, without a restart, and the rule is listed with origin "panel"

#### Scenario: Rule without a source refused
- **WHEN** the developer saves a rule with no source
- **THEN** it is refused naming the rule and `source`, and the rules in force are unchanged

#### Scenario: Rule reset to the file
- **WHEN** the developer edited `shelf-bracket-count` and then resets it
- **THEN** the checked-in version is in force again

#### Scenario: Invalid override does not stop startup
- **WHEN** a stored rule cites an owner note that was deleted, and the service starts
- **THEN** the service starts, the rule is not applied, and the panel shows it as invalid, naming the missing note

#### Scenario: Checked-in table untouched
- **WHEN** the developer edits any rule
- **THEN** `config/design_rules.yaml` is unchanged
