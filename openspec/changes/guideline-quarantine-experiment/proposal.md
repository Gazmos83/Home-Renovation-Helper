## Why

The current guideline corpus can contain uploaded or checked-in PDFs indexed with only a licence note; the Berlin RAG brief requires documented authorisation before extraction and embeddings. Evaluate the effect of quarantining that legacy content in an isolated test branch before deciding whether to change the owner's normal chatbot.

## What Changes

- Implement this experiment only on `test/guideline-quarantine`, in a separate worktree created from a coherent foundation baseline. Use a dedicated experiment database, separate automated-test database, copied guideline files and separate render/upload roots. A Git branch alone does not isolate PostgreSQL or files.
- Depend on the [RAG foundation](../furniture-engineering-rag-foundation/proposal.md) registry and rights decisions; do not create a competing source registry.
- Audit legacy guideline publications, uploads, owner-note provenance and hardware-sheet mirrors. Map them to source versions where possible; mark unmatched or undocumented content `pending_review`, with a reason. Do not treat a citation, a PDF purchase or the word "personal" as permission.
- Exclude quarantined text/vectors from vector, keyword and hybrid retrieval and from onward model/trace exports. Preserve copied files, metadata and existing rows for inspection; the quarantine operation does not delete them.
- Show links/metadata and the reason when an affected source has no usable content. Release a source only after a documented rights decision and successful provenance-preserving re-ingestion; release does not make technical values verified automatically.
- Compare baseline and quarantined retrieval on identical furniture questions. Report coverage lost, useful answers retained, unsupported answers, source traceability and latency; preserve ordinary design, cut-list and pricing behaviour.
- Quarantine does not automatically delete quoted design rules or change frozen hardware inputs. Report rules linked to quarantined publications as preliminary/unverified; prevent them being used as verified engineering evidence. A later promoted change must decide any removal or recalibration of those rules explicitly.
- Produce an evaluation and promotion recommendation. Running the experiment does not authorise merging, enabling quarantine in the normal app, or touching its database.

**BREAKING within the experiment only:** previously searchable undocumented guideline content becomes unavailable, and experiment uploads are held for rights review rather than indexed at once. The default app retains its current corpus throughout the experiment.

**Ladder step:** none. **Agents:** Designer and Researcher receive fewer guideline passages in the experiment; no new agent or model. **Render guard and bpy allow-list:** unaffected; evaluation requires no render.

## Capabilities

### New Capabilities

- `guideline-quarantine`: isolated experiment, source audit, reversible retrieval exclusion, release and comparative evaluation.

### Modified Capabilities

- `design-guidelines`: in the experiment, legacy publications and mirrored notes/sheets require rights decisions before indexing or returning their text.

## Impact

- Reuse foundation source/version eligibility, existing ingestion entry points, `search_guidelines`, source listing/upload routes and their tests. Audit direct `index_page` callers for notes and hardware sheets so they cannot bypass the experiment gate.
- **Conflicts:** current publication and developer-upload specs promise immediate searchability; a separate worktree still inherits production DSNs and absolute file defaults; cited bracket rules can keep numbers even when their source text is quarantined. This proposal includes a scoped spec replacement, startup isolation checks and rule-status reporting.
- `dev-panel-insights` must be at a coherent baseline for its upload paths; `conversation-memory-settings` must not let historical source text or summaries bypass a quarantine decision.
- Branch creation, copied-data setup and quarantine are future apply tasks. Current uncommitted work must not be switched, stashed or committed implicitly; the apply workflow chooses a coherent snapshot before creating the experiment.
- Estimate: **2–4 additional developer days** (16–32 hours), medium confidence, assuming the foundation supplies the shared registry and filters. Document-rights decisions and any future production promotion are excluded. This does not repeat the foundation effort.
