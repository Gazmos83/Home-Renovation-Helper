## Why

The furniture-engineering RAG already serves Berlin residential pieces, but kitchen base/wall/tall cabinets, drawers, hinges, moisture zones and appliance fit need dedicated namespaces, source records and safety gates. Extending the existing registry and retrieval keeps one corpus and avoids a second RAG stack.

## What Changes

- Add ten kitchen logical collections as additional `Collection` values on the existing engineering source/version tables; dual-tag overlapping sources onto existing collections (`material_datasheets`, `hardware_manuals`, `furniture_standards_index`, `eu_de_berlin_law`, `product_safety`, `engineering_fundamentals`) so nothing is duplicated or re-embedded.
- Extend source metadata with optional kitchen product/constraint fields (manufacturer, model, part number, runner/hinge constraints, `source_kind`, explicit embedding-approval flag) while keeping legacy rows valid with nulls.
- Seed link-only catalogue entries for kitchen DIN/EN candidates, EGGER/Blum/Hettich/Häfele indexes, accessibility and appliance/worktop placeholders; no full-text crawl without recorded rights.
- Add kitchen query-intent routing that expands searches to kitchen namespaces plus related existing collections under DE/EU jurisdiction filters.
- Extend code-rendered missing-input / `NOT VERIFIED` gates for shelves, drawers, runners, hinges, wall anchoring, moisture, appliances, worktops and cross-manufacturer substitution; refuse DIN-compliance claims without cited tests.
- Reuse existing calculator families (`shelf_*`, `joint`, `hardware`, `anchor`, `tipping`, `countertop`); add kitchen furniture kinds on assessment inputs; leave methods unavailable until their release packages exist.
- Add regression and kitchen acceptance tests; publish a migration report of mappings, link-only sources and unresolved licensing/numeric evidence.

No render-guard or bpy allow-list change. Ladder step: Researcher (lookup) and Designer (revision with engineering context). Agents: Researcher and Designer via existing engineering plugins.

## Capabilities

### New Capabilities
- `kitchen-engineering`: Kitchen cabinet/drawer namespaces, catalogue seeding, intent routing, license-gated metadata and kitchen-specific `NOT VERIFIED` validation rules on top of the existing engineering RAG.

### Modified Capabilities
- (none in main `openspec/specs/`; engineering-knowledge / engineering-safety remain in the unarchived foundation change. This capability composes with that foundation without replacing it.)

## Impact

- Backend: `app/engineering/schemas.py`, `chat.py`, retrieval/search filters, `config/engineering_sources.yaml`, assessment furniture kinds, tests, migration report under `docs/`.
- Plugins: existing `engineering_knowledge` / `engineering_calculators` reused; no new plugin.
- Database: no destructive migration; collections remain a string array; new enum values are additive; optional metadata fields are null for legacy rows.
- Dependencies: active `furniture-engineering-rag-foundation` and `furniture-engineering-calculators` behaviour preserved; methods stay unreleased.
