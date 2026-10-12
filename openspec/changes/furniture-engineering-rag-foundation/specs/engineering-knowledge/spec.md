## Purpose

Defines how engineering sources, rights decisions, document versions and structured numerical evidence become attributable, applicable knowledge for furniture designed in Berlin.

## ADDED Requirements

### Requirement: Engineering sources have versioned catalogue metadata
The service SHALL register sources separately from their content and preserve identifiable editions/revisions. It SHALL support the logical collections `engineering_fundamentals`, `material_datasheets`, `hardware_manuals`, `furniture_standards_index`, `eu_de_berlin_law`, `product_safety` and `murphy_bed_safety`. Source/version and passage metadata SHALL include publisher, title, source URL, standard or model, edition, retrieval time, jurisdiction, applicable furniture, material grade, thickness in mm, licence status, page/section and verification status. Unknown or inapplicable fields SHALL be explicitly null rather than invented. A metadata-only record SHALL require no extracted text or vector.

#### Scenario: Link-only standard registered
- **WHEN** DIN EN 14749 is registered without approved content-use rights
- **THEN** its identifier, edition when known and official URL are listable, with no extracted passage or embedding

#### Scenario: Editions share a URL
- **WHEN** a manufacturer's changed manual replaces a file at the same URL
- **THEN** both document revisions remain identifiable and the earlier revision's evidence is not silently overwritten

### Requirement: Content processing requires documented rights for its scope
Engineering content SHALL NOT be fetched for ingestion, text-extracted, embedded or retrieved without a current documented rights decision permitting the relevant operation and exact version/blocks. Approval SHALL record supporting terms/permission, reviewer, timestamp and any scope/expiry. A free-text licence note, purchase, citation, local-file location or public download SHALL NOT alone establish approval. Remote model use and retention/commercial use SHALL be recorded separately from local embedding rights. A model SHALL NOT set or approve rights.

#### Scenario: Unreviewed PDF
- **WHEN** a developer registers a local PDF with only a "personal reference" note
- **THEN** the record stays pending/link-only, and the engineering ingestion path performs no text extraction or embedding

#### Scenario: Incomplete approval refused
- **WHEN** an approval lacks a supporting rights reference or an operation scope
- **THEN** it is refused naming the missing field and the source remains ineligible

#### Scenario: Rights revoked during ingestion
- **WHEN** a source's permission is revoked after extraction but before publication
- **THEN** no new searchable version is published and subsequent retrieval excludes its content

### Requirement: Remote model requests recheck excerpt eligibility
Only engineering excerpts with current rights permitting remote model use SHALL be included in an OpenRouter request. This boundary SHALL also cover source-derived property values, table/equation blocks and report evidence; changing their representation SHALL NOT bypass recorded scopes. Sources permitted for local search only SHALL yield metadata/links to cloud agents. Request assembly SHALL recheck current decisions for newly retrieved and historical engineering content; revoked/ineligible content SHALL be omitted from the request copy, with a stated evidence limitation. Stored local history SHALL NOT be destructively rewritten by request fitting.

#### Scenario: Local search permitted but remote use absent
- **WHEN** a matching passage permits local embedding but no remote use
- **THEN** the model receives metadata/link and the limitation, but no passage text

#### Scenario: Historical excerpt revoked
- **WHEN** earlier tool results or a summary contain an engineering excerpt whose rights were revoked
- **THEN** the next model request excludes that text and does not use the summary as substitute evidence

#### Scenario: Property record cannot bypass remote rights
- **WHEN** a local-only table value has been converted into a typed property record or report evidence
- **THEN** its source-derived content stays outside the remote request and the evidence limitation is reported

### Requirement: Engineering ingestion preserves complete evidence blocks
Approved PDF, HTML and Markdown content SHALL retain section hierarchy, page references, source revision, table row labels/headers/units/footnotes and equation definitions/conditions. A numerical value SHALL NOT be detached from its product, grade, thickness, test/load conditions or units. Unreadable or ambiguous blocks SHALL be reported for review and SHALL NOT become verified numerical evidence. Local paths SHALL remain confined; remote content SHALL respect identity, robots, SSRF, pacing and refusal restrictions without expanding permitted retail pricing sources.

#### Scenario: Material table spans a page boundary
- **WHEN** an approved table has its headers on one page and a thickness row on the next
- **THEN** the retrieved row carries its headers, unit, grade, conditions and both relevant page references

#### Scenario: Equation damaged by extraction
- **WHEN** extraction cannot reliably retain an equation's symbols or units
- **THEN** the block is marked for review and no verified engineering property is generated from it

#### Scenario: Approved source refuses fetching
- **WHEN** robots rules or the host refuse an approved engineering URL
- **THEN** ingestion reports the refusal, keeps metadata and does not retry through another identity or route

### Requirement: Ingestion publishes atomically and preserves usable versions
An engineering version SHALL become searchable only after its authorised blocks and provenance have passed validation. A failed refresh SHALL preserve the prior usable version only while its rights remain valid. Unchanged authorised content SHALL reuse its vectors, while rights and verification changes SHALL take effect independently of text changes. Default search SHALL distinguish current and superseded editions; explicitly requested historical evidence SHALL be labelled as such.

#### Scenario: Refresh fails
- **WHEN** extraction fails while updating an existing rights-approved version
- **THEN** the last usable eligible version remains available, with the failed refresh reported

#### Scenario: Rights change without text change
- **WHEN** permission is withdrawn but the document hash is unchanged
- **THEN** its content immediately becomes ineligible despite reusable vectors

### Requirement: Numerical properties are typed and independently reviewed
Structured numerical records SHALL retain exact product/grade/source revision, page/section, canonical and original units, exact value or range, relevant conditions, value basis and verification status. Supported fields SHALL cover elasticity in MPa, bending strength in MPa, density in kg/m³, capacity in N, thickness in mm and cited allowable spans in mm. Missing values SHALL be null. A citation or automatically extracted candidate SHALL NOT by itself verify a value. Mean/test strength SHALL NOT be silently treated as allowable resistance; a range SHALL NOT be narrowed to a midpoint.

#### Scenario: Unknown elasticity
- **WHEN** an identified board's source supplies thickness but no verified elasticity
- **THEN** thickness is retained and elasticity stays null/unverified

#### Scenario: Similar product rejected
- **WHEN** a candidate value names another grade, thickness or hardware model
- **THEN** it cannot satisfy the requested product's verified property

#### Scenario: Range preserved
- **WHEN** a reviewed source states a property as a range
- **THEN** the record and retrieval retain both bounds and the source conditions

### Requirement: Engineering eligibility is enforced before ranking
Engineering retrieval SHALL apply rights, collection, applicable furniture/jurisdiction, edition, model, grade and thickness filters before ranking or limiting results, consistently for semantic, keyword and hybrid search. Default retrieval SHALL return applicable current evidence or explicitly state uncertainty. Metadata-only matches SHALL be separated from supporting passages. Conflicting applicable values SHALL be shown with their conditions, not averaged. Every passage and owner-authored field SHALL reach the model inside neutralised untrusted-content delimiters with its attribution.

#### Scenario: Ineligible nearest result
- **WHEN** an unauthorised or mismatched-model passage ranks closer than an eligible passage
- **THEN** the former is excluded before the result limit and only eligible evidence is returned

#### Scenario: Empty engineering corpus
- **WHEN** no applicable authorised evidence matches
- **THEN** retrieval states no evidence was found and never fills the answer with legacy guideline text

#### Scenario: Source conflict
- **WHEN** two applicable source versions give different values under different conditions
- **THEN** both values and conditions are reported as a conflict requiring resolution

#### Scenario: Injection in a manual
- **WHEN** a manual passage instructs the agent to bypass rights or change tools
- **THEN** it remains delimited data and cannot change eligibility or tool permissions

### Requirement: Engineering text is excluded from external tracing
Engineering source text SHALL NOT be exported to Langfuse through tool results, prompts, model outputs, errors, summaries or later calls carrying that text. Trace metadata SHALL be limited to opaque evidence identifiers, outcomes, timings and usage for those content-bearing calls. Local token accounting SHALL continue, and tracing failure SHALL NOT block a turn.

#### Scenario: Engineering call traced
- **WHEN** a traced turn uses an engineering excerpt and its reply paraphrases that excerpt
- **THEN** the exporter receives neither the content-bearing input nor output, while identifiers, duration and usage remain observable

#### Scenario: Later summary contains engineering content
- **WHEN** a summary call would include an earlier engineering tool result
- **THEN** its content-bearing trace fields are suppressed too
