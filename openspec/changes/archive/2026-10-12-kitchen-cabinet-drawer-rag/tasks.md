## 1. Schemas and collection mapping

- [x] 1.1 Add the ten kitchen `Collection` values and optional kitchen metadata fields on `SourceMetadata`; verify Pydantic accepts legacy sources with nulls and rejects invalid URLs as before
- [x] 1.2 Add collection-mapping helpers (kitchen ↔ existing dual-tags) and verify unit tests cover each of the ten namespaces without renaming existing collection IDs

## 2. Catalogue seed and license gate

- [x] 2.1 Extend `config/engineering_sources.yaml` with kitchen dual-tags on existing rows and new link-only DIN/EN, Hettich, Häfele, accessibility and appliance/worktop entries; verify `seed-links` registers metadata only (zero chunks/embeddings) in a test
- [x] 2.2 Confirm ingestion still refuses unapproved embedding (`approved_for_embedding` false / missing `Scope.EMBED`) for a copyrighted-standard fixture; verify the existing rights tests still pass

## 3. Routing and safety validation

- [x] 3.1 Add kitchen intent detection and recommended collection expansion; verify base/wall/sink, drawer, hinge, hanger/anchor, moisture, appliance, ergonomics and worktop intents route to the expected kitchen + related collections
- [x] 3.2 Extend `missing_inputs` / answer gates for drawers, hinges, moisture, appliances, cross-manufacturer refusal and DIN-compliance refusal; verify the Codex acceptance queries return `NOT VERIFIED` with the named missing inputs
- [x] 3.3 Extend assessment furniture kinds for kitchen cabinets/drawers/worktops mapped to existing calculator families; verify unavailable methods still return `NOT VERIFIED` and no formula is released

## 4. Tests and migration report

- [x] 4.1 Add regression coverage that prior material/hardware/Murphy/shelf engineering queries and collection filters still work
- [x] 4.2 Run serial backend pytest for engineering kitchen/registry/retrieval/chat/calculation modules against the designated test database and fix failures from this change
- [x] 4.3 Write `docs/kitchen_rag_migration_report.md` listing created/mapped namespaces, indexed vs link-only sources, tests run, and unresolved licensing or numerical evidence
