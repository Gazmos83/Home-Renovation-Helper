## 1. Shared baseline and persistence

- [x] 1.1 Select the coherent migration/admin/memory baseline at apply time and record dependencies on active changes; verify the selected revision contains the required upload and memory interfaces without committing or stashing unrelated work.
- [x] 1.2 Add source/version, rights-decision and ingestion-run schemas with all brief metadata and seven logical collections; verify null/unknown handling, immutable version identity and append-only decisions in database tests.
- [x] 1.3 Add separate engineering chunk/property tables and migration using the existing 1024-dimensional embedder; verify migration and legacy retrieval against unchanged retailer/guideline rows.

## 2. Rights and content boundaries

- [x] 2.1 Implement version/block-scoped rights decisions, supporting evidence, expiry and separate extraction/embedding/retrieval/remote/retention/commercial scopes; verify missing evidence, expiry and revocation deny the relevant operation.
- [x] 2.2 Gate source staging and ingestion before fetching/extracting, then recheck before embedding/publication; verify unapproved sources remain metadata-only and a mid-job revocation prevents publication.
- [x] 2.3 Implement the final remote-request eligibility check and historical request-copy sanitisation; verify a locally eligible but remotely denied or newly revoked excerpt, property value or report evidence never reaches the fake OpenRouter transport.

## 3. Provenance-preserving ingestion

- [x] 3.1 Implement page/section-aware PDF paragraph blocks and physical/printed page labels; verify fixture excerpts retain their source version and page after chunking.
- [x] 3.2 Implement table/equation blocks with headers, units, footnotes and conditions, plus reviewed manual transcriptions; verify ambiguous/scanned blocks remain review-pending and cannot supply verified values.
- [x] 3.3 Preserve HTML/Markdown heading and table structure through the existing safe fetch/path controls; verify refused hosts, unsafe URLs and escaped local paths never become ingestion inputs.
- [x] 3.4 Add staged atomic publication, failed-refresh handling and unchanged-text vector reuse; verify failures retain only still-eligible prior evidence and metadata/rights changes apply even when vectors are reused.

## 4. Numerical records and retrieval

- [x] 4.1 Add reviewed property candidate/editing flows with original/canonical units, ranges, value basis and exact product/test conditions; verify unknown is null and no extraction candidate becomes verified automatically.
- [x] 4.2 Implement engineering vector, keyword and hybrid queries with eligibility and applicability filters before top-k; verify denied versions and wrong model/grade/thickness/edition cannot fill results in any mode.
- [x] 4.3 Return typed evidence and separate metadata-only hits, with full provenance and conflicting values; verify contradictions are preserved and a link-only hit cannot support a numerical claim.
- [x] 4.4 Add the toggleable Designer/Researcher lookup plugin and engineering adapter for existing guideline calls; verify an empty/disabled engineering lookup does not fall back to legacy content.

## 5. Chat, memory and tracing

- [x] 5.1 Bind engineering intent in application context and update specialist routing; verify standalone engineering questions reach Researcher, revisions reach Designer and visual discrepancies still reach Reviewer.
- [x] 5.2 Add the typed engineering answer envelope and code-rendered verification/status fields; verify malformed/unsupported claims yield NOT VERIFIED, foundation replies disclose unavailable calculations and ordinary dimensional edits keep their confirmation flow.
- [x] 5.3 Add furniture-specific missing-input/review gates for wall fixings, TV/climbing, countertops and Murphy beds; verify hanger evidence, visual approval or a generic manual cannot satisfy the required exact installation evidence.
- [x] 5.4 Persist evidence IDs/qualifications separately from summaries and fit complete evidence blocks to the existing budget; verify truncated history never becomes a source and insufficient space produces reduced whole evidence or an insufficient-evidence result.
- [x] 5.5 Suppress content-bearing Langfuse exports for engineering and subsequent excerpt-carrying title/summary calls; inspect a fake exporter for prompts, tools, answers and errors while verifying opaque IDs/timings/usage and local metering remain available.

## 6. Developer controls and initial sources

- [x] 6.1 Add developer-gated source, rights, ingestion and property APIs; verify unauthenticated/disabled gates, rejection of unsupported approvals and unchanged legacy upload behaviour outside engineering registration.
- [x] 6.2 Add the knowledge admin page and eligible retrieval preview using existing UI patterns, shown as the Engineering Knowledge view of the Design Studio's Design Knowledge tab (`/admin/design-knowledge/engineering`); verify pending/link-only/rights-approved/technically-reviewed states remain distinct in browser checks on that view.
  Browser pass 2026-10-15: headless Chromium through Python Playwright 1.63 on `/admin/design-knowledge/engineering`. Scratch database `home_renovation_dk_check` and scratch guideline, upload and render folders, dropped and deleted afterwards. Backend on 8132 (scratch owner login, developer panel on, gateway probe and Langfuse off, a scratch OpenRouter key, RunPod settings blank) and the current `vite build` on 5212; the owner's 8000 and 5173 were untouched. No model call, no render. 9 of 9 checks passed, no page errors (only the 401 before sign-in).
  - Three sources registered from the view as metadata only. **Pending:** "Link-only / pending", "Rights pending / revoked / expired", "unverified". **Rights-approved** (Local use preset, reviewer and evidence entered): "Link-only / pending", "Rights approved", "unverified". **Technically reviewed** (approved, one-page PDF staged, authorised ingestion published 1 block, source review "verified"): "1 blocks (published)", "Rights approved", "verified by Owner check". Each row reads differently.
  - "Approved only" hides the pending source; "Verified only" shows only the reviewed one. A reload keeps all three states.
  - The retrieval preview returned the reviewed source as eligible evidence and neither the pending nor the rights-approved-only source.
  - At 360 × 780 the view and the states show with the page 360 px wide.
  - **Finding (not changed):** registering a source before the source list's first load finishes (about 1–3 s on a cold backend) leaves the new row unlisted until the next refresh: the post-registration refetch joins the still-running first request. Not seen when the list has loaded first; left for the owner.
  - `config/engineering_acceptance.json` now records `browser_checks: passed` with this evidence (owner's go-ahead, 2026-10-15). The engineering plugin stays off until enabled by hand.
- [x] 6.3 Register the brief's initial source metadata/official links and document rights-review inputs; verify registration alone causes no content download, extraction or vector insertion.
- [x] 6.4 Add bounded reviewed local-file/CLI ingestion for large authorised documents; verify the normal upload limit remains intact and mixed-rights source blocks are selectively excluded. Real source ingestion requires recorded rights evidence first.

## 7. Evaluation and release

- [x] 7.1 Prepare at least 24 labelled English/German retrieval/answer cases over an authorised fixture corpus, with development and held-out subsets; verify coverage includes exact identifiers, conflicting values, missing inputs and all specified hazard gates.
- [x] 7.2 Measure Recall@5, citation/condition completeness and cold/warm latency with real local embeddings; tune on the development subset, verify zero denied-source returns and record held-out results and remaining quality gaps.
- [x] 7.3 Run chatbot regressions for confirmation, revisions, cut lists, prices and visual approval using mocked model/Blender boundaries; verify zero false verified-capacity/conformity claims and zero excerpt-export violations in the acceptance cases. No render is required.
- [x] 7.4 Run required backend checks serially against the designated test database and frontend lint/test/build checks; verify they pass, record results and resolve failures attributable to this change.
- [x] 7.5 Document source review, administration, local quality/latency results and disable-feature rollback; verify the plugin is enabled only after the acceptance evidence is recorded and no global quarantine or calculator method is enabled by this change.
