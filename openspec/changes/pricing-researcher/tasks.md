## 1. Price list

- [ ] 1.1 Migration `0004_pricing_corpus` (all ten tables, indexes, seeds) and models; verify upgrade/downgrade on the test database and no autogenerate drift
- [ ] 1.2 Add settings (`RETAIL_SOURCES`, `CRAWLER_CONTACT`, `TOOM_HOME_STORE`, pacing, page budget, rate limits) and port `ingestion/robots.py`, `fetcher.py`, `live_fetcher.py` (unreadable robots = refusal); verify `tests/test_ingestion_rules.py`, `tests/test_ingestion_fetcher.py`, `tests/test_live_fetcher.py` ported with an unknown source failing startup by name
- [ ] 1.3 Port `pricing/price_list.py` with provenance (`captured|manual|snapshot`) and override; verify `tests/test_price_list.py` covers a manual entry, a panel without a sheet size refused, override beside the base, refresh changing only the captured price, refresh of a manual entry refused, and delete refused for an entry a pricing used
- [ ] 1.4 Add the product-page parser and `POST /price-list/from-url` writing entry and chunks in one transaction; verify `tests/test_price_list_from_url.py` with the toom fixtures covers a captured panel with sheet size, a non-toom host refused, 403 and robots refusals creating nothing, and a parse gap 422
- [ ] 1.5 Port snapshots with `prefill`; verify `tests/test_snapshots_api.py` covers a snapshot in the corpus, a prefilled `snapshot` entry, a future date refused, and delete refused while an entry references it

## 2. Corpus and retrieval

- [ ] 2.1 Port `embedding.py` (bge-m3, CPU torch index, `Embedder` protocol), `db/chunk_store.py`, `retrieval.py`; verify `tests/test_chunk_store.py` and `tests/test_retrieval.py` with a fake embedder, and `tests/test_embedding.py` marked `slow`
- [ ] 2.2 Port `ingestion/{sources,sitemap,extract,pipeline}.py` and the CLI for toom; verify `tests/test_ingestion_pipeline.py` (idempotent re-ingestion, robots-disallowed pages skipped)
- [ ] 2.3 Port `prompts.Passage`/`wrap_passage(s)` and the tools `search_catalog_knowledge`, `check_live_listing`, `compare_products`; verify their ported tests plus an injection fixture asserting wrapping and neutralisation

## 3. Pricing

- [ ] 3.1 Port the home store (`stores`, services, restrictions, `--store` ingestion, routes); verify `tests/test_store_home.py` covers a restriction outranking a captured service
- [ ] 3.2 Port `pricing/pricing.py` (`material_key`, `pack_sheets`, classification, charge modes, banding, hardware, delivery, `Personal_Supply`) keyed by package version from `input.json`; verify `tests/test_pricing_packing.py`, `tests/test_pricing.py` cover the desk priced complete, a remnant used first with the rack unchanged, an unknown hardware line making it incomplete, a part too large listed, and reprice creating a second immutable record
- [ ] 3.3 Add pricing and remnant routes and the gated `manage_remnants` and `price_cut_list` tools; verify `tests/test_pricing_api.py` and `tests/test_remnants.py` (add via chat pauses, rack unchanged until `yes`)

## 4. Design guidelines

- [ ] 4.1 Write `config/guideline_sources.yaml` (Bauordnung Berlin, Musterbauordnung, ASR A1.2/A1.8/A3.4), confirming each URL and its robots, and the `--guidelines` ingestion with `pypdf` and section splitting; verify `tests/test_guideline_ingestion.py` with a PDF fixture yields sectioned `guideline` chunks with title, section and date, and a refused source is reported and skipped
- [ ] 4.2 Add `guideline_notes` routes mirrored into the corpus and `search_guidelines`; verify `tests/test_guidelines_api.py` covers create/edit/delete reaching the corpus, a citation required, and search results wrapped with their source
- [ ] 4.3 Write `config/design_rules.yaml` (each limit quoted from its clause) and `app/guidelines/checks.py` with the four checks; apply placement rules in `room_fit` and piece rules in `create_piece`/`revise_package` previews; verify `tests/test_design_rules.py` covers each check, a `warn` in the summary naming rule, value, limit and source, a `refuse` refusing with no pause, and a rule without a source failing startup by id

## 5. The Researcher

- [ ] 5.1 Add `researcher.md`, extend `KNOWN_TOOLS`, `SPECIALISTS`, the Foreman's decision and rules, and give the Designer `search_guidelines`; verify `tests/test_foreman.py` routes a price question to the Researcher, `tests/test_instructions.py` loads five files, and a missing `researcher.md` fails startup naming it
- [ ] 5.2 Run the pricing loop against fake models: built piece → "what will it cost?" → `price_cut_list` → reply with total and missing lines; verify `tests/test_pricing_loop.py` asserts the stored pricing and that the reply cites prices only from it

## 6. Studio SPA

- [ ] 6.1 Scaffold `frontend/` (Vite, React, TypeScript, Tailwind, shadcn/ui, TanStack Query, React Router, Vitest, oxlint, pnpm) with `lib/api.ts`, auth and the layout; verify `pnpm test`, `pnpm lint`, `pnpm build` pass and a 401 returns to sign-in in a component test
- [ ] 6.2 Port the price-list page and entry form (list, filter, add, edit, override, refresh, paste URL); verify component tests and a browser pass recorded here (add, override, refresh, a refused URL)
- [ ] 6.3 Add the snapshots, remnants and guideline-notes pages; verify component tests and a browser pass recorded here for each (create, delete, one refusal)

## 7. Documentation and verification

- [ ] 7.1 README: settings, ingestion commands (`--store`, toom, `--guidelines`), the price-list routes with `curl`, the frontend commands; `.env.example` gains the new settings with `TOOM_HOME_STORE` marked `TODO(user)`; tick CLAUDE.md §11 step 5
- [ ] 7.2 Run `uv run ruff check .`, `uv run pytest -m "not slow"`, `uv run pytest --blender -m blender` (no render added; every render at `draft`), and `pnpm lint && pnpm test && pnpm build`; verify all pass and record the counts in the commit message
