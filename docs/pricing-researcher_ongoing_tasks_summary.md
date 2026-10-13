# Pricing Researcher — Ongoing Tasks Summary

Updated: 2026-10-07

The [shared recommendations](https://chatgpt.com/s/t_6ac63ee974d481918384f53551888a5c) provide useful source leads, but are insufficient to complete tasks **4.1** and **4.3** on their own. Both tasks already have their code and tests implemented; their source and rule configurations remain empty.

## Task 4.1 — guideline corpus

- Obtain permitted copies of Bauordnung Berlin, Musterbauordnung, and relevant BAuA rules, including ASR A1.2.
- Store local documents under `docs/guidelines/` and populate `backend/config/guideline_sources.yaml` with publication metadata and licence notes.
- Use URL sources only where the host permits this service's access; report and skip refusals.
- Run guideline ingestion and verify searchable passages retain their title, section, date, and citation.

USDA Wood Handbook, manufacturer manuals, AWI, and appropriately licensed DIN/EN documents are potential supplementary sources. Preserve their jurisdiction and application conditions; they do not replace the planned building and workplace publications.

## Task 4.3 — design rules

Populate `backend/config/design_rules.yaml` with exact cited clauses supporting the four existing checks:

- Front clearance.
- Unobstructed door swing.
- Piece or worktop height range.
- Shelf span by board thickness.

Use verified original clauses or explicit, cited owner notes. Confirm applicability before enabling rules. The shelf-span check currently lacks material, load, and support distinctions.

The recommended door gaps, reveals, hinge quantities, and moisture classes require additional checks and design inputs if they are to be enforced.

## Completion

Verify actual ingestion and rule behavior, update affected tests, and record the results before checking off 4.1 and 4.3. Then reconcile related task 7.1 and `CLAUDE.md` §11 step 5.

See [the detailed tracking document](pricing-researcher_ongoing_tasks.md) for the full checklist. These documents do not complete the tasks; no ingestion or tests were run while writing them.
