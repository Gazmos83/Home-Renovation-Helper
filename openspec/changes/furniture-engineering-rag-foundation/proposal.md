## Why

The app already retrieves furniture guidelines, but its free-text licence notes, flattened PDF extraction and retailer-calibrated search cannot establish whether engineering evidence is authorised, applicable or complete. Implement the foundation recommended in `docs/berlin_furniture_rag_codex_brief.md` so the existing chatbot can give sourced preliminary engineering advice while reporting missing verification honestly.

## What Changes

- Reuse local `BAAI/bge-m3` (1024 dimensions), PostgreSQL/pgvector, hybrid search, existing agents, owner authentication and token budgets. Represent the brief's seven collections as logical partitions, without another vector service or model slot.
- Add a versioned source registry, documented rights decisions, provenance-preserving PDF/HTML/Markdown ingestion, and structured material/hardware properties. Unknown values remain null; rights approval and technical verification are separate decisions.
- Gate extraction, embedding and retrieval by documented rights. Sending excerpts to existing OpenRouter models requires a separate documented remote-use scope. Engineering excerpt text is excluded from Langfuse exports, including tool results, prompts, answers and summary calls.
- Seed source metadata and official links from the brief. USDA content is indexed only after reviewing the applicable rights and third-party elements; DIN/EN, EU/Berlin and manufacturer sources start link-only. Website access and a local PDF are not embedding permission.
- Give Designer and Researcher an engineering lookup path with exact product/revision, grade, thickness, jurisdiction and applicability filters. Existing `search_guidelines` calls during an engineering turn use the same eligibility rules; there is no fallback to unreviewed legacy content.
- Engineering replies show assumptions, loads, dimensions, exact product/grade, source/page, missing inputs and `NOT VERIFIED` where appropriate. Foundation replies explicitly say that numerical engineering calculation is not implemented. Visual approval, successful geometry generation and drilling completeness do not imply load capacity or conformity.
- Keep ordinary design/revision, pricing and visual-review workflows. Engineering replies can ask more questions and have additional retrieval latency. They do not require an engineering questionnaire for a purely dimensional revision.
- Keep existing guideline files/chunks intact. Global legacy quarantine belongs to the separate [quarantine experiment](../guideline-quarantine-experiment/proposal.md); deterministic calculations belong to [engineering calculators](../furniture-engineering-calculators/proposal.md).

**Ladder step:** supports step 1 with evidence; no generator extension or live Blender work. **Agents:** Foreman (engineering intent), Designer and Researcher (lookup/replies); Intake and Reviewer retain their existing responsibilities. **Render guard and bpy allow-list:** unaffected.

## Capabilities

### New Capabilities

- `engineering-knowledge`: source registry, rights scopes, seven collections, structured numerical evidence, versioned ingestion and retrieval.
- `engineering-safety`: evidence-backed answer contract and mandatory furniture-specific safety gates, independently of calculations.

### Modified Capabilities

- `design-agents`: distinguish engineering evidence questions from visual review and ordinary design changes; use engineering lookup without adding a specialist.
- `design-guidelines`: keep legacy guidelines as preliminary guidance and prevent their use as verified engineering evidence without review.
- `dev-panel`: manage engineering sources, rights decisions, technical verification, ingestion state and property records.
- `token-budget`: preserve engineering evidence conditions across prompt fitting and memory compression.

## Impact

- Extend `backend/app/db/models.py` and migrations; reuse `embedding.py`, `retrieval.py`, `db/chunk_store.py`, `guidelines/{sources,ingest,uploads}.py`, plugin manifests, prompts and the existing tracing wrapper. Add an engineering service and developer routes/page; retain the current guideline upload page for legacy sources.
- Source identity must support stable editions rather than the existing `(url, chunk_index)` replacement key. Every retrieval mode must apply the same eligibility filters; the current vector-only path does not carry category filtering. Engineering relevance thresholds require their own bilingual evaluation rather than reusing toom thresholds blindly.
- **Conflicts:** `design-guidelines` currently allows local copyrighted files on possession alone; `dev-panel-insights` uploads index immediately; shelf/bracket rules omit load/material conditions and extrapolate beyond their table; memory compression cuts tool results; Langfuse currently masks email only. Design and deltas explicitly bound these behaviours rather than silently treating them as engineering approval.
- Coordinate with active `dev-panel-insights`, `conversation-memory-settings` and `room-version-approval`. Their files are already partly implemented in the working tree; select a coherent migration head at apply time. Partial-divider behaviour is now archived and part of the current baseline.
- Estimate: **12–20 developer days** (96–160 hours at 8 hours/day), medium confidence. Breakdown and acceptance evaluation are in `design.md`. Rights clearance, owner document supply and qualified review are external dependencies, not included elapsed time.
- This proposal changes planning artifacts only. Implement and enable it through a later explicit apply request; it performs no quarantine, database change or model call now.
