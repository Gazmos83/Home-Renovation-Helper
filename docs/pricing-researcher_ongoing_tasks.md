# pricing-researcher_ongoing_tasks

Updated: 2026-10-07

This document records the remaining work for pricing-researcher tasks **4.1** and **4.3**, based on the [shared recommendations](https://chatgpt.com/s/t_6ac63ee974d481918384f53551888a5c) and the repository implementation. The change is now stored under [the archived pricing-researcher change](../openspec/changes/archive/2026-10-07-pricing-researcher/tasks.md); these tasks remain unchecked there.

The recommendations are useful source-selection guidance. They do not, by themselves, supply the publications and verified clauses needed to complete both tasks.

## Current state

| Task | Implemented | Remaining |
| --- | --- | --- |
| 4.1 — guideline ingestion | Local PDF and Markdown ingestion, robots-gated URL fetching, section splitting, provenance metadata, and tests. | Populate [guideline_sources.yaml](../backend/config/guideline_sources.yaml), which currently contains `sources: []`, and verify ingestion of the selected documents. |
| 4.3 — design rules | Strict rule loader, four checks, startup loading, placement and piece tool integration, and tests. | Populate [design_rules.yaml](../backend/config/design_rules.yaml), which currently contains `rules: []`, with rules supported by exact source clauses. |

The recorded source review on 2026-10-06 found refusals or unreadable robots rules on the official hosts. The implementation treats those as refusals and supports owner-supplied local files instead.

## Task 4.1 — supply and ingest guideline publications

- [ ] Obtain permitted copies of the planned publications: Bauordnung Berlin, Musterbauordnung, and the relevant BAuA workplace rules, including ASR A1.2.
- [ ] Place local PDFs under `docs/guidelines/pdf/` or permitted Markdown documents under `docs/guidelines/notes/`. Keep copyrighted PDFs out of Git, as configured in `.gitignore`.
- [ ] Add each publication to `backend/config/guideline_sources.yaml` with its unique `id`, title, jurisdiction, publication date, format, licence note, and either a relative `path` or an official HTTPS `url`.
- [ ] Use URL sources only when this service's identity is allowed by the host's robots rules and the document can be fetched. A refusal must be reported and skipped.
- [ ] Run guideline ingestion against the configured database and embedding model, and inspect the reported results.
- [ ] Verify that ingested passages retain their publication title, section, and date and are searchable through `search_guidelines` with their source.

From `backend/`, the ingestion command is:

```bash
uv run python -m app.ingestion --guidelines
```

### Supplementary sources from the recommendations

| Candidate | Useful content | Conditions before inclusion |
| --- | --- | --- |
| [USDA Wood Handbook](https://research.fs.usda.gov/fpl/wood-handbook) | Wood properties, moisture movement, fastenings, panels, and engineering background. The publisher provides downloads of the handbook and individual chapters. | Record the selected edition and usage terms; identify it as technical guidance from the US rather than German building law. |
| [Hettich technical guidance](https://hta-diy.hettich.com/de-de/scharniere/topfscharniere/intermat) and SIMONSWERK manuals | Product-specific hinge selection, installation, loading, and clearances. | Verify document access and usage terms; preserve the manufacturer, product, and application conditions. |
| AWI standards | Architectural joinery, installation tolerances, and cabinetry guidance. | Verify the original documents, access, and usage terms; preserve the US/AWI context. |
| DIN/EN standards | Dimensions, performance classifications, materials, and accessibility. | Verify rights to use the full text in RAG and use permitted local files. Catalogue descriptions alone do not supply the clauses required for hard rules. |

These are supplementary carpentry sources. They do not replace the building and workplace publications named in the current proposal. Broader corpus coverage should be reflected in the specification when adopted.

## Task 4.3 — supply cited, applicable design rules

Each rule needs an id, `applies_to`, a supported check and its parameters, `warn` or `refuse` severity, and `source: {publication, section, quote}`. The publication must be listed in the source configuration or reference an owner note as `owner:<note uuid>`.

| Existing check | Required evidence |
| --- | --- |
| `front_clearance_mm` | A quoted minimum clearance clause applicable to the intended placement. |
| `door_swing_clear` | A quoted requirement supporting an unobstructed door opening area. |
| `height_range_mm` | Quoted minimum and maximum heights for the intended piece or worktop. |
| `shelf_span_mm_for_thickness` | Quoted span limits for the relevant thicknesses, with compatible material, loading, and support assumptions. |

- [ ] Locate and read the original clauses supporting the selected rules. Do not use an AI summary as the source clause.
- [ ] Confirm that each clause applies to the intended home, piece, material, and use. Workplace or accessibility requirements must not silently become universal home-design limits.
- [ ] Where no suitable official clause exists, create an explicit owner note with a required citation and clearly identify any owner preference as such.
- [ ] Enter the verified parameters and exact supporting quotes in `backend/config/design_rules.yaml`.
- [ ] Confirm that the checks can represent the source's conditions before enabling a rule. Extend the specification and implementation where necessary.
- [ ] Update the shipped-table test, which currently asserts that `load_rules()` returns an empty tuple, when adding real rules.
- [ ] Verify representative compliant and breaching inputs for the populated rules, including warnings in confirmation summaries and refusals without a confirmation pause.

The shared answer's door-bottom gaps, reveals, hinge quantities, and moisture classes do not map to these four checks. Enforcing them would require additional checks and corresponding design inputs.

The current shelf-span check uses board thickness alone. It cannot distinguish material, loading, or support conditions. Likewise, most of the recommended applicability metadata is not currently represented in the source and rule schemas; a quote does not compensate for missing applicability logic.

## Verification and completion

Run the relevant existing tests from `backend/` after changing the configurations or implementation:

```bash
uv run pytest tests/test_guideline_ingestion.py tests/test_guidelines_api.py tests/test_design_rules.py
```

- [ ] Record actual ingestion results and rule verification in the change documentation.
- [ ] Mark 4.1 complete once the selected publications are configured and verified through ingestion and retrieval.
- [ ] Mark 4.3 complete once the rule table contains the required cited, applicable rules and their integration is verified.
- [ ] Reconcile the related task 7.1 documentation and `CLAUDE.md` §11 step 5 after resolving these outstanding items.

Creating this tracking document does not complete or check off the outstanding implementation tasks. No ingestion or tests were run as part of writing it.
