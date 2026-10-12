# Kitchen cabinet/drawer RAG extension — migration report

**Change:** `openspec/changes/kitchen-cabinet-drawer-rag`  
**Date:** 2026-10-11  
**Basis:** `docs/kitchen_cabinet_drawer_rag_extension.md` on the existing furniture-engineering RAG

## Created / mapped namespaces

| Kitchen namespace | Dual-tagged existing collections | Status |
|---|---|---|
| `kitchen_cabinet_engineering` | `engineering_fundamentals` | added |
| `kitchen_drawer_systems` | `hardware_manuals` | added |
| `kitchen_hinges_hardware` | `hardware_manuals` | added |
| `kitchen_panel_materials` | `material_datasheets` | added |
| `kitchen_cabinet_connections` | `engineering_fundamentals` | added |
| `kitchen_wall_anchoring` | `hardware_manuals`, `product_safety` | added |
| `kitchen_ergonomics_accessibility` | `furniture_standards_index` | added |
| `kitchen_moisture_protection` | `engineering_fundamentals`, `material_datasheets` | added |
| `kitchen_appliance_integration` | (none; kitchen-only until exact manuals) | added |
| `kitchen_structural_validation` | `furniture_standards_index` | added |

Existing seven collections (`engineering_fundamentals`, `material_datasheets`, `hardware_manuals`, `furniture_standards_index`, `eu_de_berlin_law`, `product_safety`, `murphy_bed_safety`) are unchanged. No vectors were deleted or re-embedded. Registration expands kitchen tags through `with_dual_tags()`.

## Indexed vs link-only sources

All catalogue rows in `config/engineering_sources.yaml` remain **link-only / metadata-only** (`approved_for_embedding: false`). No full-text ingestion or embeddings were produced by this change.

| Key | Kind | Embedding |
|---|---|---|
| usda-wood-handbook-2021 | handbook | link-only (third-party rights pending) |
| eu-gpsr-2023-988 | legislation | link-only (reuse terms pending) |
| berlin-bauordnung | legislation | link-only (reuse terms pending) |
| din-en-14749-2022-07 | licensed standard | link-only |
| din-en-15939-2019-11 | licensed standard | link-only |
| din-en-16122-context | standards context | link-only |
| din-en-312-particleboard | licensed standard (edition unverified) | link-only |
| din-en-622-5-mdf | licensed standard (edition unverified) | link-only |
| din-18040-2-accessibility | licensed standard (not a universal kitchen mandate) | link-only |
| egger-datasheet-index | manufacturer index | link-only |
| blum-catalogue-2022 | manufacturer catalogue | link-only |
| hettich-documentation-index | manufacturer index | link-only |
| hafele-documentation-index | manufacturer index | link-only |
| cosentino-documentation-index | manufacturer index | link-only |
| kitchen-appliance-manual-placeholder | placeholder (no URL) | link-only |
| kitchen-worktop-manual-placeholder | placeholder (no URL) | link-only |
| murphy-bed-manual-candidate | manufacturer candidate | link-only |

`Scope.EMBED` rights remain the embedding authority. Version attributes are immutable, so `approved_for_embedding` is catalogue documentation set at registration (always false for seeds); registration refuses `approved_for_embedding=true` so a seed cannot self-approve.

## Implementation summary

- Optional kitchen product/constraint metadata on `SourceMetadata` (manufacturer, part number, runner/door constraints, `source_kind`, etc.); legacy nulls preserved.
- Intent router in `app/engineering/kitchen.py`; retrieval prefers kitchen + dual-tagged collections when no explicit collection filter is set.
- `missing_inputs` / answer gates for drawers, hinges, moisture, appliances, wall anchoring, 18 mm P2 shelves, cross-manufacturer refusal, DIN-compliance refusal.
- Assessment furniture kinds: `kitchen_base_cabinet`, `kitchen_wall_cabinet`, `kitchen_tall_cabinet`, `kitchen_drawer`, `kitchen_worktop` mapped to existing unavailable calculator families (`shelf_*`, `joint`, `hardware`, `anchor`, `tipping`, `countertop`). **No method was released.**

## Tests run

```text
uv run pytest tests/test_kitchen_engineering.py \
  tests/test_engineering_registry.py \
  tests/test_engineering_retrieval.py \
  tests/test_engineering_chat.py \
  tests/test_engineering_ingestion.py \
  tests/test_engineering_calculation_contracts.py \
  tests/test_engineering_reports.py -q
# 100 passed
```

Acceptance behaviours covered: 18 mm P2 shelf, 40 kg runner, plasterboard anchors, Blum→Hettich refusal, DIN EN 14749 compliance refusal, oven clearance without model, copyrighted DIN embed refusal, legacy Murphy/material filters.

## Unresolved licensing / numerical evidence

- **DIN EN 14749, 15939, 312, 622-5, 18040-2, EN 16122:** licensed; no clause text; editions for 312/622-5/18040-2 not verified beyond catalogue index links.
- **EGGER, Blum, Hettich, Häfele, Cosentino:** public indexes only; exact product PDFs and embedding rights pending.
- **Appliance / worktop manuals:** placeholders without URL or model; owner must supply exact manuals under rights review.
- **USDA Wood Handbook:** public-domain candidate; third-party elements still need review before embedding.
- **EU GPSR / BauO Bln:** official links; reuse terms pending before full-text use.
- **Numerical properties:** no verified `E_MPa`, runner `nominal_load_kg`, hinge ratings, or anchor capacities were entered; all remain null until primary evidence is rights-approved and reviewed.
- **Calculator methods:** still unavailable (`NOT_VERIFIED`); no safety factors or DIN conformity claims.

## Rollback

Disable the `engineering_knowledge` plugin globally or per conversation. Kitchen seeds are metadata-only. No migration downgrade is required.
