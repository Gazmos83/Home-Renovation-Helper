# Engineering knowledge administration

Engineering knowledge uses separate source/version, rights, chunk and property tables. It reuses PostgreSQL/pgvector and the cached local CPU `BAAI/bge-m3` embedder (1024 dimensions). Ordinary guideline upload, pricing, cut lists, confirmed geometry revisions and visual approval retain their own workflows. The quarantine proposal is separate and has not been applied.

## Register and review sources

Use developer **Knowledge** (`/admin/knowledge`). The brief's ten initial records are official-link metadata only, including USDA, EU/Germany/Berlin, DIN indices and manufacturer candidates. Registration never downloads or indexes a document. Unknown fields stay null. A purchased copy, publisher URL or licence note is not permission to extract, embed or send excerpts to OpenRouter.

1. Register an identifiable source version: publisher/title/public URL, exact edition/model, jurisdiction/furniture applicability, grade/thickness and licence status where known. Changed editions/content require new versions.
2. Record supporting rights evidence and reviewer. Grant only documented operations: `extraction`, `local_embedding`, `local_retrieval`, `remote_model_use`, `retention`, `commercial_use`. Record personal-home/commercial context and expiry. Decisions are append-only; revocation or an expired latest decision never falls back to an earlier approval.
3. Grants may specify physical PDF pages and known block IDs. `null` means the complete version. Extraction can be scoped to pages before blocks exist. Retaining a complete uploaded PDF requires permission to retain that complete file; limited extracted-page permissions alone do not permit staging it. Remote use is separate from local permissions.
4. Stage a PDF (50 MB browser limit). Staging does not ingest. Authorised extraction/publication is a separate action. HTML/Markdown and larger files use the confined CLI. Unsafe hosts/redirects and paths outside `GUIDELINE_ROOT` are refused.
5. Inspect provenance. PDF physical and printed pages, headings, table units/headers, footnotes and conditions stay attached. Scans, damaged equations and ambiguous layouts remain `needs_review`. Use explicitly reviewed transcription blocks for those cases. Continuous ambiguous tables retain bounded first/previous-page context and require review of the full original table, not automatic numerical verification.
6. Enter property candidates with original units, exact values or complete ranges, value basis, exact product/grade/thickness, page/section, test method and conditions. Unknown is null, never zero. An edit/create remains unverified. Review source and properties explicitly and independently of rights. Reviewed property values require new candidate identities to change.

Example operation grants (only when the stated rights have actually been documented):

```json
{
  "extraction": {"pages": [10, 11], "blocks": null},
  "local_embedding": {"pages": [10, 11], "blocks": ["reviewed-table-1"]},
  "local_retrieval": {"pages": [10, 11], "blocks": ["reviewed-table-1"]},
  "remote_model_use": {"pages": [10, 11], "blocks": ["reviewed-table-1"]},
  "retention": {"pages": null, "blocks": null}
}
```

Local preview labels supporting evidence separately from metadata-only hits. A source technically reviewed but lacking remote permission still cannot supply excerpt/property content to a cloud model. Rights are checked before top-k and again at request assembly, including stored engineering history. Source-derived values do not escape the gate by becoming JSON or a later report. Whole evidence packets must fit the current model budget; insufficient space refuses the request instead of trimming away conditions.

## CLI

From `backend/`, with the usual configured database and guidelines root:

```sh
uv run python -m app.engineering seed-links
uv run python -m app.engineering ingest-file SOURCE_VERSION_UUID relative/path/authorised.pdf
```

The CLI does not approve rights. Files must already be inside `GUIDELINE_ROOT`; extraction, retention and embedding rights are required. Hash changes require another version. Embedding runs in bounded batches; unchanged source text can reuse vectors. Publication is atomic, and a failed refresh preserves prior content only while it remains eligible. Browser upload limits are unchanged by CLI ingestion.

## Local retrieval quality

The local embedder ranks evidence; it does not generate the chatbot's answer or verify engineering. Existing OpenRouter model routing is reused. Product/grade/thickness/edition and rights filters precede semantic/keyword/hybrid ranking. A highly similar wrong model is still excluded. Exact property records and source conditions, rather than an embedding score, govern what is eligible evidence.

Recorded real-BGE evaluation: [results](../openspec/changes/furniture-engineering-rag-foundation/evaluation.json), [initial measurement](../openspec/changes/furniture-engineering-rag-foundation/evaluation-initial.json). The 26 original English/German synthetic cases split into 12 development and 14 held-out cases. Hybrid development Recall@5 was 100%, held-out 92.6%; vector held-out 88.9%; keyword held-out 88.9% after development-driven token matching. Citation/condition completeness was 100%; denied-source returns and false verified claims were zero in every mode. Thresholds selected on development only are hybrid 0.3, vector 0.5, keyword 0.0.

Cold model initialisation measured 13.3 seconds; warm retrieval median 211 ms and maximum 321 ms on this machine. These are small-fixture CPU timings, not a production SLA. The generic missing-product/load question missed some labelled board passages; it remains unverified and requests inputs. Exact filters often left very few candidates. This corpus does not establish accuracy on real manufacturer PDFs, large books, unreviewed OCR, arbitrary products or engineering methods. New actual documents need extraction inspection and representative evaluation before relying on their evidence.

Repeat the evaluation serially against `TEST_DATABASE_URL` naming a designated `*_test` database (never an application database):

```sh
uv run python -m app.engineering.evaluate --output ../openspec/changes/furniture-engineering-rag-foundation/evaluation.json
```

Fixture writes roll back; the command uses real local embeddings and makes no OpenRouter or Blender call. Fixture products/ratings are fictitious and never registered as production design data.

## Chat behaviour and rollback

Standalone engineering questions use Researcher; engineering revisions of an existing piece use Designer and retain normal geometry confirmation. Reviewer remains a visual discrepancy reviewer. Engineering replies use validated source/property selections and code-rendered units, provenance, assumptions and missing inputs. The foundation has no numerical method and labels capacity/conformity `NOT VERIFIED`. Hanger ratings do not establish wall capacity; TV/child climbing, exact countertop instructions and matching Murphy-bed manual/anchorage/qualified review have separate missing-input gates.

The engineering plugin defaults off. Complete the recorded backend/frontend/browser acceptance checks before global enablement, then opt in per conversation. Engineering tracing suppresses content-bearing graph/generation callbacks and root input/output. Opaque identifiers, outcomes, timings and local token metering remain available. Later engineering source history is re-fetched under current rights; summaries cannot upgrade a value or a remembered result.

Rollback by disabling `engineering_knowledge` globally in **Plugins**, or for the relevant conversation. This stops engineering lookup; it does not revive legacy content as engineering evidence. Keep source versions, rights decisions and ingestion audits. Revoke rights separately when required. No migration downgrade, source deletion, quarantine promotion or calculator enablement is needed to disable the feature.
