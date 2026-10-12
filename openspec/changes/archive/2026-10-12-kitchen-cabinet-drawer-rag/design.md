## Context

See proposal.md for motivation. The foundation already provides `KnowledgeSource` / `KnowledgeSourceVersion` with a string-array `collections` field, rights decisions, engineering chunks/properties, hybrid retrieval, typed answer rendering and unreleased calculator families. Catalogue seeds live in `config/engineering_sources.yaml`. Kitchen work must extend those seams without a second vector store or ingestion pipeline.

## Goals / Non-Goals

**Goals:**
- Add the ten kitchen namespaces as additive `Collection` values and dual-tag overlapping sources.
- Extend nullable metadata for kitchen product/constraint fields and embedding-approval signalling.
- Seed link-only kitchen sources; keep the existing license/rights gate authoritative for content.
- Route kitchen intents to kitchen + related existing collections; extend `missing_inputs` / validation rules.
- Reuse calculator families with kitchen furniture kinds; keep methods unavailable.
- Preserve existing furniture queries and embeddings.

**Non-Goals:**
- Releasing any numerical method, inventing load ratings, or asserting DIN compliance.
- Crawling manufacturer/DIN PDFs or enabling the engineering plugins globally.
- Rebuilding catalog-knowledge (toom) RAG or changing Blender/render paths.
- Archiving the foundation change (handled separately).

## Decisions

1. **Namespaces as Collection enum values (not a parallel category column).**  
   Rationale: filters already use `collections.contains([...])`; adding enum members is additive and needs no destructive migration. Dual-tag kitchen sources onto existing collections to avoid duplicate identities.  
   Alternative considered: a free-text `namespace` metadata field only — weaker typed filters and easier typos.

2. **Mapping table (logical kitchen → also tag existing when overlapping).**  
   | Kitchen namespace | Also map / dual-tag |  
   |---|---|  
   | `kitchen_panel_materials` | `material_datasheets` |  
   | `kitchen_drawer_systems`, `kitchen_hinges_hardware` | `hardware_manuals` |  
   | `kitchen_structural_validation` | `furniture_standards_index` |  
   | `kitchen_wall_anchoring` | `hardware_manuals`, `product_safety` |  
   | `kitchen_cabinet_engineering`, `kitchen_cabinet_connections`, `kitchen_moisture_protection` | `engineering_fundamentals` (and materials when panel-specific) |  
   | `kitchen_ergonomics_accessibility` | `furniture_standards_index` / law when DIN 18040-2 |  
   | `kitchen_appliance_integration` | (kitchen-only until exact manuals exist) |  
   Existing seven collections remain primary for non-kitchen queries.

3. **Metadata extension on `SourceMetadata`.**  
   Add optional: `source_kind`, `approved_for_embedding` (default false), `manufacturer`, `part_number`, `variant`, and constraint scalars (`nominal_load_kg`, `runner_length_mm`, `drawer_width_mm`, `drawer_depth_mm`, `door_height_mm`, `door_mass_kg`, `panel_thickness_mm`, `mounting_conditions`). Keep `standard_or_model` as the exact model/SKU field already used by filters. Ingestion still requires `Scope.EMBED` rights; the metadata flag alone never authorises embedding.

4. **Intent routing in application code.**  
   Extend `engineering_intent` keywords for kitchen German/English terms. Add `kitchen_query_intents(text) -> list[Collection]` and `related_collections(intents)` that expand to kitchen + mapped existing collections. The search tool accepts an explicit `collection` filter today; routing helpers produce recommended filters for the plugin/chat path and for tests. Multi-collection search: run filtered searches per collection (or unfiltered with post-preference) without changing ranking maths; prefer returning union of eligible evidence with collection tags preserved.

5. **Safety gates in `missing_inputs` / answer rendering.**  
   Add kitchen-specific missing-input phrases for drawers/runners, hinges, moisture/P2-vs-humid, appliances, worktops (already partially covered), wall cabinets (already covered), and explicit refusals for cross-manufacturer substitution and DIN-compliance assertions. Keep calculator methods returning `unavailable()` / `NOT_VERIFIED`.

6. **Assessment furniture kinds.**  
   Extend `AssessmentIn.furniture` with `kitchen_base_cabinet`, `kitchen_wall_cabinet`, `kitchen_tall_cabinet`, `kitchen_drawer`, `kitchen_worktop` (worktop may alias existing `countertop` checks). Map these to existing method families; do not add new formula implementations.

7. **Seeding.**  
   Update `config/engineering_sources.yaml`: retag existing DIN/EGGER/Blum/Cosentino/EU/Berlin rows with kitchen collections where applicable; add DIN EN 312, DIN EN 622-5, DIN 18040-2, Hettich, Häfele, generic appliance/worktop placeholders as link-only. `seed-links` remains idempotent by key+attributes.

## Risks / Trade-offs

- [Risk] Collection enum growth makes filters noisier → Mitigation: dual-tag carefully; intent router selects a small set per query; tests cover both kitchen and legacy filters.
- [Risk] Multi-collection search increases tool calls → Mitigation: helper returns a bounded collection list; default limit unchanged; no remote crawl.
- [Risk] Metadata fields unused until real manuals arrive → Mitigation: nulls are explicit; migration report lists unresolved numeric evidence.
- [Risk] Foundation change still unarchived → Mitigation: kitchen capability is self-contained; compose with foundation tables already in the codebase.

## Migration Plan

1. Deploy code with additive enum/metadata; no table rewrite.
2. Run `uv run python -m app.engineering seed-links` to register new/updated metadata rows (creates new versions when attributes change; does not delete old vectors).
3. Rollback: disable `engineering_knowledge` plugin; kitchen seeds are metadata-only and harmless; optional revert of catalogue YAML leaves prior versions intact.

## Open Questions

None that block implementation; exact appliance/worktop manuals remain owner-supplied later under rights review.
