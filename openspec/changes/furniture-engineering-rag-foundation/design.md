## Context

See `proposal.md` for motivation and the owner decisions. The current implementation already has CPU-local BGE-M3, a shared `chunks` table with HNSW/German full-text search, `search_guidelines` for Designer/Researcher and a lawful fetcher. `guidelines/ingest.py` joins all PDF pages into plain text before 1200-character chunks; source metadata has no technical verification, page range or machine-enforced rights. `retrieval.py` thresholds were measured on toom, and its vector-only path ignores categories.

The current working tree contains active upload/admin, memory and approval work. Investigation is based on those files as found, not just HEAD. `partial-and-folded-dividers` has since been archived; current shelf geometry includes partial dividers and folds.

## Goals / Non-Goals

**Goals:** Preserve a complete engineering evidence chain, distinguish content-use rights from technical suitability, and improve the existing chatbot without changing its models or furniture geometry.

**Non-Goals:** Structural calculations, global legacy quarantine, certification, replacing the gateway, a local answering LLM, automatic rights approval, an unattended crawler, general OCR or arbitrary diagram/table interpretation. Unsupported document blocks are reported for manual review instead of becoming numerical evidence.

## Decisions

### 1. Three changes with one shared foundation

The owner selected foundation first, separate quarantine and calculator proposals, reuse of the stack, and rights-approved excerpts to OpenRouter. Foundation adds a new engineering path; quarantine changes legacy retrieval only in an experiment; calculators add reviewed methods later. An alternative that immediately quarantines the main corpus would change current answers before the owner can evaluate the loss and is outside the chosen scope.

The foundation does not certify the remaining legacy ingestion policy. Ordinary legacy guidance remains available outside engineering turns until a separately reviewed quarantine promotion. Legacy content cannot silently become engineering evidence.

### 2. Versioned engineering tables beside the existing corpus

Use the same PostgreSQL database and BGE-M3 embedder, with `knowledge_sources`, `knowledge_source_versions`, append-only `knowledge_rights_decisions`, `engineering_chunks`, `engineering_properties` and ingestion-run records. A separate engineering chunk table avoids rewriting retail upserts keyed on `(url, chunk_index)`. Reuse search/scoring and passage-wrapping code through an eligibility-aware engineering adapter rather than a second database/service.

Each chunk belongs to one immutable source version and has a stable ordinal/block identity. A version belongs to any of these logical collections:

| Collection | Role |
|---|---|
| `engineering_fundamentals` | Mechanics and general wood/composite evidence |
| `material_datasheets` | Exact product, grade and thickness properties |
| `hardware_manuals` | Exact hardware model and installation revision |
| `furniture_standards_index` | Standard metadata, scope and approved text if later licensed |
| `eu_de_berlin_law` | Jurisdiction and project-specific applicability evidence |
| `product_safety` | Hazards and safety obligations within their scope |
| `murphy_bed_safety` | Matching mechanism manuals and installation evidence |

Metadata contains all brief fields: `publisher`, `title`, `source_url`, `standard_or_model`, `edition`, `retrieved_at`, `jurisdiction`, `applicable_furniture`, `material_grade`, `thickness_mm`, `license_status`, `page_section`, `verification_status`. Also retain language, content hash, PDF physical/printed page labels, local-file identity, supersession and reviewer timestamps. Fields that do not apply are explicitly null; unknown editions/grades are never invented. `source_url` is the public citation when known, distinct from a confined local file path. Metadata-only records need no extracted content or vector.

### 3. Rights scopes checked at every content boundary

A rights decision records supporting terms/permission reference, reviewer, timestamp, allowed versions/pages/blocks, expiry if stated and distinct scopes for extraction, local embedding/retrieval, remote model use, retention and commercial use. `approved_for_embedding` is derived from the current decision, not a model-set boolean or a non-empty licence note. Record the current personal-home use; do not infer commercial rights or legal applicability from that.

Unapproved sources are registered as metadata/URL only and are not fetched or text-extracted by the engineering ingester. If the developer already possesses a file, byte/type/size/hash checks can stage it locally without extracting or indexing its contents; retention also needs an authorised basis. Rights become valid only through the developer gate. Owning a PDF does not authorise external processing. Reject a rights approval without supporting evidence, and never infer permission from robots.txt.

Check rights before extraction, before writing embeddings, before each retrieval, and immediately before assembling an OpenRouter request. This catches revocation while a job or conversation is in progress. Remote-use permission is independent: locally embeddable content without remote permission yields only source metadata to cloud agents. Historical engineering tool results and summaries containing now-ineligible source text are omitted/replaced in request copies; the local conversation remains intact subject to its retention rights. No model can authorise a source.

This boundary also covers source-derived property values, table rows, equation blocks and report evidence. Converting a passage into JSON or a calculator report does not bypass its recorded remote-use scope. Reports must track those source associations so later request assembly can return only permitted content and identify unavailable evidence.

### 4. Provenance-first ingestion with atomic publication

Reuse the existing path confinement, identity, robots, pacing, refusal and safe-network restrictions. Engineering source registration does not expand the toom pricing allow-list. Arbitrary URLs supplied to admin must also pass SSRF restrictions; a link-only record requires no content request. A host refusal remains a refusal even when the source has rights approval.

Parse PDF pages separately, track section hierarchy and physical/printed pages, and represent paragraphs, tables and equations as typed blocks. Keep table headers, row labels, units and footnotes with each row; attach equation symbols and conditions. Repeated headers are permitted for context, but a numerical value must not be detached from grade, thickness, orientation, product/revision or test condition. HTML tables are parsed structurally before prose extraction. Engineering Markdown retains headings and structured tables.

Use the existing parser where it preserves the required information. A scanned page, ambiguous table or damaged equation is flagged `needs_review`; it cannot populate verified numerical properties. A reviewed manual block/transcription with a page reference is the first-version escape hatch. A layout/OCR dependency requires a measured need and separate decision rather than silently trusting a new parser.

Build a version in staging, validate blocks, embed authorised text in bounded batches and publish atomically. A failed refresh retains the last technically usable version if its rights remain valid; failure never retains access to revoked text. Unchanged content can reuse vectors, but rights/verification metadata changes still apply. Superseded editions stay identifiable; default retrieval uses a current applicable edition, and explicit historical retrieval labels it as such.

### 5. Structured numerical records are reviewed, not mined facts

Use typed property records keyed to source version, page/section and exact product/grade. Property kinds include `E_MPa`, `bending_strength_MPa`, `density_kg_m3`, `capacity_N`, `thickness_mm` and `allowable_span_mm`. Store exact values or min/max ranges with canonical units, original notation, test method, moisture, orientation, duration, temperature/support/loading conditions where relevant, and `value_basis` (for example mean, characteristic or allowable).

Unknown is null, never zero. Unit conversion is deterministic and retains the original. Values enter as reviewed developer records; extraction can prepare candidates but cannot verify them. Owner notes and existing hinge/shelf-pin drilling sheets can be linked to records, but neither their citation nor correct drill dimensions establishes resistance. No generic USDA wood property is silently assigned to a specific EGGER board.

### 6. Retrieval eligibility precedes ranking

Add `search_engineering_knowledge` to a toggleable engineering-knowledge plugin for Designer and Researcher. Query filters cover collection, jurisdiction, furniture type, source edition, exact model, material grade and thickness. Session, piece and conversation scope come from application context, never tool claims. Source decisions and product filters are applied before top-k in hybrid, keyword and vector searches; no text from an ineligible source can fill a short result set.

Keep multilingual BGE-M3 and add engineering lexical handling for English/German prose and literal product/standard identifiers. The current German full-text rank is useful but is not a sufficient English technical benchmark. Start with the current hybrid mechanism and tune engineering thresholds on an approved fixture corpus. A reranker is deferred unless benchmark failures justify its CPU/memory cost. BGE-M3's model card recommends hybrid retrieval and reranking, but that does not establish accuracy for this corpus: [BAAI model documentation](https://huggingface.co/BAAI/bge-m3).

Return delimited excerpts, full attribution and a machine-readable evidence envelope. Metadata-only hits are separate from evidence hits and cannot support numerical claims. Conflicting applicable values are both reported with their conditions; do not average them or automatically declare a winner. `search_guidelines` routes to the eligible engineering adapter during engineering turns, so a disabled engineering plugin or an empty search cannot trigger a legacy fallback.

### 7. Chat gates protect claims while preserving the design workflow

Extend Foreman intent handling: standalone engineering questions go to Researcher, even without a room; a requested piece revision stays Designer; a visual discrepancy stays Reviewer. Both evidence specialists receive engineering tools, while Builder still works from validated JSON. An engineering intent flag is fixed in application state before tool binding and cannot be removed by a retrieved passage or editable prompt.

Engineering answers use a typed envelope validated by code and a renderer for the safety/status portion: assumptions, owner loads and dimensions, exact product/grade, evidence IDs with pages, missing inputs, warnings and calculation status. Narrative explanation can be model-authored, but cannot set verification flags, material values or conformity status. Reject an invalid engineering envelope and return a fixed `NOT VERIFIED` response; do not rely on a model promise or a keyword blacklist. The foundation has no enabled calculation methods.

| Owner request | Foundation behaviour |
|---|---|
| Make a cabinet wider | Existing restate/confirm/revise workflow; no unrelated load questionnaire |
| Find a suitable board | Applicable evidence and product conditions, with remaining unknowns |
| Can the shelf hold 30 kg? | Loads can be recorded explicitly; no calculated safe capacity; `NOT VERIFIED` and required inputs |
| Does the shelf look aligned? | Existing visual Reviewer; no structural approval |
| Is a Murphy bed safe to install? | Requires matching manual, wall/anchor assessment and qualified review; no final safe-to-build claim |

Higher-risk replies also identify substrate/load distribution, TV/child-climbing scenarios or material-specific countertop support instructions. The brief's statement that DIN EN 15939 concerns hangers is a scope guard, not evidence of wall-fixing strength. DIN references remain standard metadata, not laws or proof of tested conformity. Berlin building/GPSR applicability is checked per project, especially because this is currently a personal-home app.

Current dimensions, parts and prices still derive from stored spec/house data. Evidence that recommends changing a dimension feeds the normal owner-confirmed revision; retrieval cannot write geometry or alter a render tier.

### 8. Privacy, memory and developer controls

Add `/admin/knowledge` for source metadata, rights decisions, ingestion/review state, property editing and eligible retrieval previews. Reuse the existing gate (401 without session, 404 when disabled). Keep the legacy `/admin/guidelines` workflow until the separate experiment; an engineering registration/upload never takes that immediate-index path.

Engineering excerpt text is excluded from Langfuse at the export boundary, not merely by omitting one tool span. Suppress content-bearing inputs/outputs for the entire engineering turn and any future summary/title/other call whose context carries engineering excerpts, including copied answers. Export only opaque evidence IDs, outcomes, timings and usage. Local metering and trace links continue. Tests use a fake exporter to inspect prompts, tools, outputs, errors and summary calls. Existing email masking remains.

Persist evidence identifiers and qualification fields separately from prose history so memory compression cannot promote a summary to a source. On each later engineering question, re-fetch eligible evidence; a 300-character historical tool fragment is insufficient. If the complete evidence packet cannot fit the context budget, reduce the number of whole passages or refuse/return insufficient evidence; never cut off conditions to retain a number.

## Risks / Trade-offs

- [Initially few rights-approved sources] → Honest link-only answers and `NOT VERIFIED`; document supply/rights review is a dependency, not a parser workaround.
- [PDF table/equation fidelity] → Typed blocks, human review for ambiguity and real-document extraction fixtures before a value is verified.
- [CPU cold start and larger corpus] → Keep one cached embedder and small batches; measure warm/cold retrieval and ingestion throughput. No latency guarantee is invented.
- [Unreviewed legacy guidance remains outside engineering] → Explicitly scope the foundation, keep evidence eligibility fail-closed and evaluate broader quarantine separately.
- [A model produces unsupported narrative] → Structured claims/status validation, adversarial answer cases and fixed insufficient-evidence response; this cannot establish real-world conformity.
- [Remote rights or retention change] → Versioned decisions, late request check and request-copy sanitisation; administrative removal handles storage separately.

## Migration Plan

1. Apply after selecting a coherent baseline/migration head for the active admin/memory changes. Add tables and engineering interfaces without altering existing chunks, specs or saved hardware inputs.
2. Register catalogue metadata/link-only records; approve only reviewed document versions/blocks and rights scopes. The USDA publisher identifies FPL-GTR-282, 2021, and a 103.95 MB download, which also exceeds the current 50 MB upload cap: use reviewed local-file/CLI ingestion in bounded batches, not an unexplained upload-cap increase. [USDA catalogue](https://research.fs.usda.gov/treesearch/62200)
3. Validate mocked boundary tests and a small approved real corpus before enabling the engineering plugin. Keep normal chatbot regression examples in the same evaluation.
4. Roll back by disabling the engineering feature/plugin and routes, leaving new records for inspection. Do not downgrade/drop evidence tables in order to recover ordinary chat, or rewrite legacy records. Rights restrictions remain authoritative for any engineering excerpt already in request history.
5. Broader quarantine and engineering methods require their separate apply workflows. Do not sync their deltas into the main specs during this planning task.

## Effort and acceptance

One developer familiar with this codebase, 8-hour person-days; estimates include meaningful tests and browser checks, exclude licence acquisition and external review.

| Work | Days |
|---|---:|
| Registry, rights scopes, schema/migrations | 2–3 |
| Provenance blocks and ingestion lifecycle | 3–5 |
| Structured properties and engineering retrieval | 2–3 |
| Chat envelope, remote/trace gate and memory integration | 2–4 |
| Developer UI, evaluation and regressions | 3–5 |
| Total | **12–20** |

Use at least 24 representative English/German question cases over an authorised fixture corpus: exact material grades/thicknesses, similar hardware models, edition mismatch, missing input, conflicting values, link-only standards, wall fixings, TV misuse, countertop supports and Murphy beds. Every denied source/product case must return zero ineligible evidence; every numerical evidence item must keep its unit and page/conditions. For answerable cases record Recall@5 against manually labelled source blocks and citation correctness; document failures and tune on a development subset, then rerun a held-out subset. Release requires no false verified-capacity/conformity claims in the case set and no regression of ordinary design confirmation, cut lists or pricing. These finite cases are acceptance evidence, not a certification.

## Open Questions

`TODO(user)` operational inputs that do not change this contract: supply the exact manufacturer document/model for the first product; nominate the person who reviews a source's technical facts; provide rights evidence for each candidate document. Until supplied, those records remain pending/link-only. No embedding or external-use permission is assumed by this proposal.
