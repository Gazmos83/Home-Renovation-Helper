# Implementation record

Apply follows the RAG foundation contracts and its automated evidence checks. The foundation browser acceptance check remains pending because the session has no connected browser. Neither feature is enabled for production, and no numerical method is released before foundation acceptance and its own qualified review.

The closed registry reserves the approved bounded method families. Unknown equations, limits and independent reference cases remain absent, rather than being populated from memory. Method source packages and a qualified reviewer are operational inputs explicitly required by the approved design. No assertion of qualification or rights is manufactured by the implementation.

## Implemented contracts and integration

Tasks 1.1–1.5, 4.1–4.3, 5.1–5.3 and 6.4 are implemented and verified. Migration `0022_engineering_assessments` follows the foundation migration and has been exercised only on the designated test database. Assessments/reports and method decisions are immutable; estimates require the dedicated owner-confirmation action. All numerical method families remain unimplemented and unavailable, with no source-backed equations, criteria or reviewed reference cases invented to satisfy the remaining tasks.

The targeted calculator contract/report/admin run passed **38 tests**, including explicit graph yes/no confirmation, finite/unit/basis/range validation, exact cited comparison boundaries, geometry exclusions, deterministic unavailable reports, immutability, geometry/fact/property/method/rights staleness, scope denial, local-only cloud protection, complete on-demand conditions, append-only method decisions and independent visual approval. These infrastructure tests do not satisfy tasks 6.1/6.2's independent engineering reference requirements. No real model call or Blender invocation occurred.

The knowledge/method UI passes its component tests; the full frontend run passes **237 tests**, lint and production build. The broad serial backend regression run passed **2,303 tests**, with 39 skipped and 21 deselected. After the final conflict/unit/reviewer-validation refinements, **183 engineering/Foreman/instruction/summary tests passed**; backend lint and strict OpenSpec validation pass. Task 6.3 is complete and calculator progress is **13/26**. The source-backed numerical-family tasks, independent reference/review validation and deletion-conflict task remain unchecked. Browser acceptance remains pending. Operational and rollback documentation is in `docs/ENGINEERING_CALCULATORS.md`.

## Deletion conflict discovered during apply

`house_file.delete_version` first renames the version folder, commits database deletion, and then calls `storage.discard_version`, which uses `shutil.rmtree(..., ignore_errors=True)`. Move/database failures restore the version, but post-commit cleanup failures are deliberately ignored. The calculator scenario requires records to remain when folder removal fails, which is stronger than this baseline. The question has been surfaced to the owner; task 4.4 remains unchecked. Existing deletion behaviour has not been silently changed or described as stronger than it is.
