## Why

The owner's goal is to build the furniture, and a board list with a realistic materials total is worth more than a prettier render (DESIGN_NOTES "Why pricing stays"). The predecessor priced cut lists against toom, but live lookup reached only products already in the corpus, manual snapshots never reached the price list, and manual entries were not visibly available. CLAUDE.md §5a reworks that into one price list with three lawful ways in, and §3 gives the Researcher the toom live data, the price list and the catalog RAG. The owner also asked for **architectural guidance**: official building and workplace rules the agents can cite, and hard numbers enforced in code rather than left to the prompt. This is §11 step 5, and it starts the Vite + React SPA (§2) with the pages pricing needs.

## What Changes

- **Price list** (`supplier_prices`): one table, toom only (`RETAIL_SOURCES=toom`). Each entry has a provenance — `captured` (fetched from a toom page), `manual` (made by hand), `snapshot` (prefilled from a manual snapshot) — and an optional owner `override` layered on top; the effective price is the override when set, else the base, and both stay visible. Three ways in: **paste a toom product URL** (robots-checked fetch, parsed, the entry created with its captured price and the page added to the corpus in one step — closing the "only corpus products" gap), **a manual entry** (key, label, category, unit, price, sheet size for panels), **a manual snapshot** of a page the crawl cannot reach, which may prefill an entry. Refresh re-fetches a captured entry and never touches its override. A 403 or a robots refusal is an answer, never retried under another identity.
- **Cut-list pricing** (port of `price_cut_list`): material keys, grain-locked first-fit-decreasing sheet packing with kerf, remnants first, cut classification against **one home toom store**'s cut services and the owner's restrictions (`covered` / `custom` / `undetermined`, notes needing review flagged), the cut-charge choice (`shared` / `per_cut`), edge banding in whole bundles, hardware and delivery lines, and `Personal_Supply`. Each pricing is an immutable record per package version; an unpriced part marks the pricing incomplete, never guessed. A **remnant rack** with a gated `manage_remnants`.
- **Catalog knowledge**: the predecessor's toom ingestion (own robots parser, paced fetcher with a stated identity, sitemaps, text extraction and chunking), local `BAAI/bge-m3` embeddings (1024) in pgvector, hybrid retrieval (vector + German full text), the live listing and spec parsers, `check_live_listing`, `compare_products`, and every retrieved passage wrapped as untrusted content with its source.
- **Design guidelines** (new): (1) a **guideline corpus** — the Bauordnung Berlin, the Musterbauordnung and the BAuA workplace rules (ASR), ingested from their official publications, plus **owner-written notes** entered by hand with a cited source — searchable through `search_guidelines` with each passage cited; (2) a checked-in **design-rules table** of hard numbers, each with its source clause, applied in code by `room_fit` and by the Designer's create/revise previews: a breach is a named warning the owner sees before saying `yes`, or a refusal where the rule says so.
- **Researcher** (new specialist): routed on its slot (`openai/gpt-5.6-luna`), with `search_catalog_knowledge`, `check_live_listing`, `compare_products`, `price_cut_list`, `manage_remnants` and `search_guidelines`. The Designer also gets `search_guidelines`. The Foreman may route to the Researcher.
- **Studio SPA starts** (`frontend/`, Vite + React + TypeScript, Tailwind + shadcn/ui, TanStack Query, React Router, Vitest, pnpm): sign-in, the **price list** (list and filter, add entry, edit, set/clear override, refresh, paste a toom URL), **snapshots** (add with optional prefill, list, delete), **remnants**, and **guideline notes**. Ported from the predecessor's `PriceListPage`/`PriceEntryForm`/`SnapshotsPanel`. Each page gets a browser pass before it counts as done (§5a).
- **Not included**: general web lookups beyond toom and the guideline sources (step 7, as a declarative HTTPS plugin on an allow-listed host); the full toom store directory (one home store only); quotes, projects and clients (dropped by §7); Bauhaus, Kaufland, OKI (excluded, not deferred); DIN standards and copyrighted guides (not ingested).

**Ladder step and agent:** no ladder step changes — pricing reads a version's derived cut list; guideline warnings appear in step-1 previews. Agents: Researcher (new), Designer (`search_guidelines`, rule warnings in previews), Foreman (routes to the Researcher). **Render guard:** not affected. **bpy allow-list:** not affected.

## Capabilities

### New Capabilities
- `price-list`: the supplier price list, provenance and override, the three ways in, refresh, and the lawful-source boundary.
- `cut-list-pricing`: pricing a package version's cut list against the price list and the home store, remnants, completeness, immutable pricing records.
- `catalog-knowledge`: toom ingestion, the corpus and embeddings, hybrid retrieval, live lookup, comparison, and untrusted-content wrapping.
- `design-guidelines`: the guideline corpus (official sources and owner notes), `search_guidelines`, and the design-rules table applied in code.
- `studio-ui`: the SPA shell, sign-in, and the price-list, snapshot, remnant and guideline-note pages.

### Modified Capabilities
- `design-agents`: the Foreman may route to the Researcher; the Researcher runs on its slot; `room_fit` and the Designer's previews apply the design rules.

## Impact

- Backend: `app/pricing/` (price list, packing, pricing, remnants, store), `app/ingestion/` (robots, fetcher, sources, sitemap, extract, pipeline, guideline sources), `app/embedding.py`, `app/retrieval.py`, `app/db/chunk_store.py`, `app/guidelines/` (rules loader and checks), `app/agent/tools/{search_catalog_knowledge,check_live_listing,compare_products,price_cut_list,manage_remnants,search_guidelines}.py`, `app/agent/instructions/researcher.md`, routes `app/api/{price_list,snapshots,pricing,remnants,guidelines}.py`, migration `0004_pricing_corpus`; `config/design_rules.yaml`, `config/guideline_sources.yaml`.
- Dependencies: `beautifulsoup4`, `defusedxml`, `pypdf`, `sentence-transformers`, CPU-only `torch` (uv index as in the predecessor). Tests use a fake embedder; real-model tests are marked `slow`.
- Frontend: new `frontend/` package; `pnpm install`, `pnpm test`, `pnpm lint`, `pnpm build`.
- Settings: `RETAIL_SOURCES`, `CRAWLER_CONTACT`, `TOOM_HOME_STORE`, ingestion pacing and page budget, rate limit for refresh and URL capture.
- Fixtures: the predecessor's toom HTML pages; a guideline PDF excerpt.
