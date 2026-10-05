## Context

See proposal.md. The predecessor (`Interior_Design_App/backend`) holds the pieces to port, with these known shapes:
- `supplier_prices` (captured/override columns, `unconfirmed`, derived `effective_cents`; no provenance column), `product_snapshots` (separate, never reaching the price list), `cut_list_pricings` + `cut_list_pricing_entries` (entry FK `ON DELETE RESTRICT`), `remnant_sheets`.
- `domain/price_list.py` (create/revise/override/refresh), `domain/pricing.py` (`price_cut_list`: `material_key`, `pack_sheets` FFD shelf packing with 4 mm kerf and remnants first, `classify_cut` against `store_directory`, banding bundles, charge modes, `Personal_Supply`), `domain/remnants.py`.
- `ingestion/` (`PacedFetcher` with `InteriorDesignAppBot/0.1 (+contact)`, own `robots.py`, toom `sources.py`, `sitemap.py` with defusedxml, bs4 `extract.py` with 1200/120 chunking, idempotent `pipeline.py`, `stores.py`), `embedding.py` (bge-m3, sentence-transformers, CPU torch from the PyTorch CPU index), `db/chunk_store.py` (hybrid 0.7 cosine + 0.3 German `ts_rank`, thresholds 0.34/0.48), `live_fetcher.py` (TTL cache, refusal statuses 401/403/429), `live_listing_parser.py`, `live_spec_parser.py`, tools `search_catalog_knowledge`, `check_live_listing`, `compare_products`, `price_cut_list`, `manage_remnants`.
- `prompts.py` `Passage`/`wrap_passage(s)`; frontend `PriceListPage`, `PriceEntryForm`, `SnapshotsPanel`, `CutRestrictionsPanel` (React 19, Vite 8, Tailwind 4, shadcn, TanStack Query, oxlint).

This repo has none of it yet: no corpus table (only `EMBEDDING_DIMENSIONS = 1024` and the `vector` extension), no `wrap_passage`, no frontend, no Researcher instruction file. The Foreman graph, `AgentTool` (preview/run, gated), `ToolContext`, the house file and `cut_list` exist from `agent-loop`.

Constraints: lawful sources only (§5a) — a 403 is an answer; prices never guessed; untrusted-content delimiters on every retrieved chunk (§8); one model per agent; homeowner pages never show models, tokens or costs.

## Goals / Non-Goals

**Goals:**
- From a built piece, "what will the boards cost?" answered with a complete or honestly incomplete pricing, in one Researcher turn.
- A toom URL pasted on the price-list page becomes a priced entry in one step.
- Guidelines the agents cite by source, and hard numbers checked by code in `room_fit` and the Designer's previews.
- The SPA exists, with the four pricing and guideline pages browser-checked.

**Non-Goals:**
- General web search or arbitrary URLs (step 7 plugin); other retailers; the store directory beyond one store; quotes and offers.
- Chat UI, Studio viewer, dev panel pages (later changes; step 7 adds toggles and the dev panel).
- Feedback learning (step 9).

## Decisions

1. **Provenance is a column, override stays separate.** `supplier_prices`: `key` unique, `label`, `category` (`panel|hardware|finish|edge_band|cut_service|delivery`), `unit` (`per_m2|per_piece|per_metre|per_cut`), sheet `length/width/thickness_mm` (required for panels by CHECK), `bundle_length_mm`, `base_cents`, `provenance` (`captured|manual|snapshot`), `source_url`, `captured_at`, `snapshot_id` FK, `override_cents`, `override_note`, `override_at`, timestamps. `effective_cents` stays derived. The predecessor's `edge_band` lived under `finish` with a `band:` key prefix; it gets its own category here. Seeds: the predecessor's dated `cut_service:*` and `delivery:*` rows as `manual` with a note, and the reserved `Personal_Supply`. *Alternative:* the predecessor's implicit provenance; rejected because §5a names four provenances and a manual entry must be distinguishable from a capture.

2. **URL capture is one transaction over two stores.** `POST /price-list/from-url {url, key, category, unit?}`: host must be in `RETAIL_SOURCES` hosts; `LiveFetcher` (robots per request, refusal statuses, no retry); a product-page parser (ported spec parser + a price block reader tested on `toom_product_3150333.html` and `toom_product_siebdruckplatte_7100576.html`) yields name, price, unit and sheet dimensions; the entry and the page's chunks (`category=product`) are written in one DB transaction; a parse gap returns 422 naming what was missing. Live lookup treats unreadable robots as refusal — a deliberate change from the predecessor's allow-all fallback, matching "a 403 is an answer".

3. **Snapshots feed the corpus and may prefill.** `product_snapshots` ported; `POST /snapshots {…, prefill: {key, category, unit}?}` records the snapshot, writes its chunks (`category=manual_snapshot`, dated `captured_on`), and with `prefill` creates a `snapshot`-provenance entry. Deleting a snapshot removes its chunks and is refused while a `snapshot` entry references it.

4. **One home store.** `TOOM_HOME_STORE` names a store slug; tables `stores` (one row in practice), `store_services`, `store_cut_restrictions` are ported so `classify_cut` keeps its three outcomes and the owner-restriction precedence. `python -m app.ingestion --store` ingests only the home store's page; no sitemap of all markets, no Berlin list. Pricing records the store key.

5. **Pricing per package version, immutable.** `cut_list_pricings` (package_id, version, computed_at, store_key, cut_charge_mode, materials_cents, cut_service_cents, banding_cents, hardware_cents, delivery_cents, total_cents, complete, counts, `result` JSONB) and `cut_list_pricing_entries` (pricing_id, entry_id `ON DELETE RESTRICT`, cents_used). Input rows come from the version's `input.json` via `derive` (the same rows `cut_list` shows), not from CSVs, so an unbuilt version can be priced. `price_cut_list` is ported with projects removed; `material_key` phrase table kept (German and English toom names).

6. **Corpus.** Table `chunks` (content, `Vector(1024)`, source_site, url, category `product|listing|policy|guide|manual_snapshot|guideline`, title, section, published_on, scraped_at, chunk_index, content_hash, generated German `tsvector`), unique `(url, chunk_index)`, HNSW cosine and GIN indexes. `chunk_store` and `retrieval` ported as they are. Embeddings: `app/embedding.py` with bge-m3 on CPU torch from the PyTorch CPU index (`[tool.uv.index]` explicit); an `Embedder` protocol lets tests inject a deterministic fake; tests loading the real model carry `@pytest.mark.slow`.

7. **Wrapping.** `prompts.Passage` and `wrap_passage(s)` ported unchanged (same sentinel already in this repo); every corpus, live, snapshot and guideline tool result goes through them; the untrusted-content guard is already composed last in every prompt.

8. **Guideline corpus.** `config/guideline_sources.yaml` lists each publication by id, title, jurisdiction, official URL(s), version/date, licence note — initially the Bauordnung Berlin (consolidated text), the Musterbauordnung (Bauministerkonferenz publication) and the ASR set used for rooms and circulation (A1.2, A1.8, A3.4 and any the apply step finds relevant), with each URL confirmed and its robots checked during apply. `python -m app.ingestion --guidelines` fetches each (PDF via `pypdf`, HTML via bs4), splits on section markers (`§ n`, `n.n` headings) before the 1200-character chunker, and stores `category=guideline`, `title`, `section`, `published_on`. Refusals are reported and skipped. Owner notes: table `guideline_notes` (title, text, value, unit, citation required) mirrored into chunks with `source_site=owner`.

9. **Design rules in code.** `config/design_rules.yaml`: `id`, `applies_to` (`placement|piece`), `check` (one of a closed set implemented in `app/guidelines/checks.py`: `front_clearance_mm`, `door_swing_clear`, `height_range_mm`, `shelf_span_mm_for_thickness`), parameters, `severity` (`warn|refuse`), `source` (`{publication, section, quote}`) — loading refuses an unknown check, a missing source, or a source whose publication is not in `guideline_sources.yaml` or an owner note id. Every limit is entered during apply by quoting the cited clause (no number is invented in planning); a rule with no official clause may cite an owner note. `room_fit` evaluates placement rules against the room polygon and openings; `create_piece`/`revise_package` previews evaluate piece rules on the derived parts; warnings appear in the result text and the confirmation summary; a `refuse` rule returns a refusal with no pause.

10. **Researcher.** `researcher.md` (slot `researcher`, tools `search_catalog_knowledge, check_live_listing, compare_products, price_cut_list, manage_remnants, search_guidelines`); `SPECIALISTS` and `slots.LOOP_SLOTS` gain `researcher` (its model is built at startup like the others); the Foreman's `Decision` gains it; code rule: `price_cut_list` refuses without a bound piece version (the tool's own refusal). `manage_remnants` add/remove is gated (subject `remnant`). The Designer header gains `search_guidelines`. `KNOWN_TOOLS` gains the six names.

11. **Routes** (owner-gated; `/admin/…` not used — pricing is the homeowner's own data): `GET/POST /price-list`, `GET/PATCH/DELETE /price-list/{key}`, `PUT/DELETE /price-list/{key}/override`, `POST /price-list/{key}/refresh`, `POST /price-list/from-url`; `GET/POST /snapshots`, `DELETE /snapshots/{id}`; `POST /packages/{id}/versions/{n}/pricings`, `GET /pricings/{id}`, `GET /packages/{id}/versions/{n}/pricings`; `GET/POST /remnants`, `DELETE /remnants/{id}`; `GET /stores/home`, `GET/PUT/DELETE /stores/home/restrictions/{kind}`; `GET/POST /guidelines/notes`, `PATCH/DELETE /guidelines/notes/{id}`, `GET /guidelines/search?q=`. Rate limits on refresh and from-url reuse the auth limiter pattern with their own keys.

12. **The SPA.** `frontend/` from the predecessor's toolchain (React 19, Vite, TypeScript, Tailwind 4, shadcn/ui components ported as needed, TanStack Query, React Router, Vitest + Testing Library, oxlint, pnpm). `lib/api.ts` (fetch with `credentials: "include"`, 401 → sign-in), `lib/auth.tsx`, a layout with navigation (Price list, Snapshots, Remnants, Guidelines). Pages ported from `PriceListPage`/`PriceEntryForm`/`SnapshotsPanel`/`CutRestrictionsPanel`, renamed to the homeowner's routes. CORS already allows `http://localhost:5173`. The browser pass is a manual walk-through recorded in `tasks.md` against `pnpm dev` + the API.

## Risks / Trade-offs

- [toom markup changes] → Parsers are fixture-tested; a parse gap is a stated 422, never a guessed price.
- [bge-m3 is a large download and slow on CPU] → Loaded lazily, once; ingestion is a CLI, not a request; tests use a fake embedder.
- [Official guideline sites may refuse robots or serve only PDFs] → Refusals are reported and skipped; the owner can add the text as notes with a citation.
- [A rule's limit is mistyped] → Every rule carries a quote of its clause; the loader refuses a rule without one; tests assert each rule's example.
- [Scope is large] → Tasks are grouped so pricing, corpus, guidelines, Researcher and SPA land and verify independently.

## Migration Plan

Migration `0004_pricing_corpus` adds `supplier_prices`, `product_snapshots`, `cut_list_pricings`, `cut_list_pricing_entries`, `remnant_sheets`, `stores`, `store_services`, `store_cut_restrictions`, `chunks`, `guideline_notes`, with the seed rows. Ingestion is run by hand after upgrade. Rollback drops the tables; the corpus is rebuilt by re-running ingestion.

## Open Questions

None that change the specs. During apply: confirm each guideline URL and its robots, quote each rule's clause, and pick the home store slug (`TOOM_HOME_STORE`, `TODO(user)` default in `.env.example`).
