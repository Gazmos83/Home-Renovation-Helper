## Context

See `proposal.md`. This experiment consumes the foundation registry/eligibility layer rather than duplicating it. Current guideline uploads call text extraction before saving and immediately index; owner notes and hardware sheets call indexing separately. Existing `design_rules.yaml` includes retailer bracket guidance and existing versions freeze those rules in `hardware_inputs.json`.

The current worktree is dirty, and only one worktree is present on branch `render-guard`. Planning does not create an experiment branch, choose which unrelated work to commit, read live database contents or mutate the corpus.

## Goals / Non-Goals

**Goals:** Measure legacy quarantine with a reversible audit trail and demonstrate that the current app's database, files and behaviour were not changed.

**Non-Goals:** Production promotion, deletion of original documents/vectors, rights adjudication by a model, changing the toom price corpus, recalculating saved drilling geometry or making historical conversation text legally reusable by retaining it.

## Decisions

### 1. Isolate data as well as Git

During apply, create `test/guideline-quarantine` in a separate worktree from a coherent revision containing the foundation. If required work is uncommitted, stop that particular setup step for a baseline decision; do not stash/switch the owner's working tree. This is a specific integration dependency, not permission to discard changes.

Use distinct `DATABASE_URL` and `TEST_DATABASE_URL` values for the experiment and its automated tests; neither may name the current app/test database. Copy required data through a read-only export without writing the source database. Use dedicated `GUIDELINE_ROOT`, `UPLOAD_ROOT` and `RENDER_ROOT`, separate port and session-cookie name. Copy, never symlink or hardlink, document files. Disable gateway startup probes, live supplier fetches and tracing for offline evaluation. Live answer evaluation, if later requested, uses rights-approved excerpts and the existing metered gateway.

An experiment startup preflight validates database identities and resolved roots against a locally recorded protected-baseline configuration; it refuses equal/overlapping protected roots, reused cookie/port and missing isolation information. Logs redact DSNs/secrets. Automated tests get their own database because test fixtures truncate tables. Evidence/reference data must not be committed.

### 2. Audit at source-version level, preserving original rows

Build an audit manifest from copied sources/uploads and guideline-category chunks, including `owner-note:` and hardware-sheet mirrors. Classify original owner-authored material separately from quotations/reproduced tables, without automatically approving every record labelled `owner`. Mark undocumented content `pending_review`; retain original content/vector and link it to source/version eligibility. Unknown mappings are excluded instead of allowing an unlinked row through.

Use foundation rights decisions as the single authority. Quarantine is an eligibility state, not a second vector index or physical move. Record affected source IDs, chunk counts, supporting/missing rights evidence, decisions, reviewer and timestamps. Local files/metadata stay inspectable behind the developer gate under their retention basis; content is never sent to cloud tools merely to decide its rights.

### 3. Close ingestion, retrieval and history bypasses

In experiment mode gate checked-in/CLI ingest, uploads, re-ingest and direct indexing for note/sheet mirrors. A PDF's readability extraction must occur after approval; pending uploads can be byte-checked/staged with an appropriate retention basis. Retrieval eligibility is checked before top-k in all search modes. Engineering rights rules remain the same as in the foundation.

A quoted legacy tool result, summary or previously returned answer must not re-export quarantined text on the next request. For evaluation, use fresh cloned conversations plus controlled historical-text tests. Sanitize request copies by evidence/source association. Where legacy history lacks reliable association, omit that history/summary from the experiment request and say it was unavailable for evidence; preserve the stored conversation for local inspection. Do not claim a keyword filter can find every copyrighted quotation.

Rights release requires a recorded decision for the exact source version/scopes and re-ingestion through the foundation block parser. A failed re-ingestion leaves the source quarantined. Revoking a decision excludes it immediately even if its vectors remain. Technical review is a separate gate.

### 4. Keep geometry and evidence status separate

Inventory design rules whose sources are quarantined and label their output preliminary/unverified; never publish their text/quoted source clauses to OpenRouter while ineligible. Existing parameter values and frozen drilling inputs are retained locally for reproducibility. Their presence can still drive ordinary preliminary geometry, but cannot verify resistance or anchorage. Removing those numerical rules would affect counts, cut lists and pricing and is excluded from this experiment. Compare those outputs against baseline explicitly.

### 5. Evaluate paired results instead of promising a quality gain

Run the foundation's bilingual question set and additional queries that presently depend on the retailer PDF, book notes or hardware mirrors. Baseline and quarantine runs use copied data and identical queries/settings; both run in the isolated environment. Measure eligible retrieval coverage, empty answers, citation completeness, false verified claims, any content-export violations and warm/cold latency. Check ordinary revisions/cut lists/pricing separately.

The report records corpus version/rights manifest, model IDs if live calls were authorised, costs/latency and differences. It includes protected-root/database integrity checks and known limitations. Reduced coverage is an expected result to quantify, not a reason to bypass the gate. Promotion is a later explicit decision and must reconcile scoped experimental specs before archive/sync; do not sync experiment-only policy into the default app automatically.

## Risks / Trade-offs

- [Shared defaults point at current data] → Explicit roots/DSNs, independent test database and startup refusal before migrations or ingestion.
- [No useful content remains for some questions] → Return metadata and reasons; include loss in the evaluation.
- [Legacy text hidden in summaries/rules] → Audit alternate content paths and request-copy sanitisation; mark copied numeric guidance unverified without altering geometry.
- [Experiment rollback confused with approval] → Restoring a copied snapshot restores experiment data only; it does not create content-use rights or enable production policy.

## Migration Plan

1. Choose the coherent foundation baseline; create branch/worktree and isolated copies/configuration during the later apply.
2. Record baseline integrity and audit mappings before applying eligibility changes to experiment data.
3. Run paired tests and produce `evaluation.md` in this change, containing metadata/metrics only, not restricted text.
4. Roll back experiment data by restoring its own snapshot or disabling experiment access while preserving the audit. Do not restore quarantined content into normal retrieval without rights approval; do not alter the source app.
5. Review the report before proposing production promotion. Keep branch/database available for inspection; cleanup is a separate explicit action.

## Effort

**2–4 additional developer days** with a completed foundation: isolated baseline/preflight, audit and legacy-path gate, release lifecycle and paired evaluation. This excludes per-document permission work, baseline conflicts that require unrelated fixes, production rollout and any live evaluation fees. Branch/database setup is planned, not performed by the proposal.
