# Codex task — Extend existing furniture RAG with kitchen cabinets and drawers

**Project context:** Existing, functioning furniture-engineering RAG for Berlin, Germany. This document is an **additive implementation specification**; do not rebuild or replace the ingestion pipeline, vector store, source registry, search API, existing collections, or calculation services. First inspect the repository and adapt the names and migration mechanism to its architecture. Read `berlin_furniture_rag_codex_brief.md` if available.

**Scope:** Residential kitchen base/wall/tall cabinets, drawer boxes, fronts and runners, hinges, hardware, worktops, moisture protection, appliance fit and installation. **Units:** mm, m, kg, N, kN, MPa (= N/mm²), kg/m³. Convert mass to force via `N = kg × 9.81` where appropriate.

## 1. Add these logical collections

Implement as physical vector collections **or** namespaced `category` filters in the existing collection, whichever fits the current system. Preserve existing collection IDs and embeddings.

| New collection / namespace | Retrieval content | Key filters |
|---|---|---|
| `kitchen_cabinet_engineering` | Base, wall, tall, sink and oven housing geometry; structural panels; backs, stretchers, plinths; assembly practices | cabinet_type, panel_thickness_mm, material_grade |
| `kitchen_drawer_systems` | Drawer-box design; full/partial extension; runners; load ratings; bottom supports and joints | manufacturer, model, nominal_load_kg, runner_length_mm |
| `kitchen_hinges_hardware` | Hinges, mounting plates, lift systems, handles, installation and load envelopes | manufacturer, part_number, door_height_mm, door_mass_kg |
| `kitchen_panel_materials` | Particleboard P2/P3/etc., MDF, plywood, coated panels, verified mechanical properties and moisture ratings | standard_grade, thickness_mm, E_MPa, moisture_class |
| `kitchen_cabinet_connections` | Dowels, confirmat screws, cams, glued joints, edge distances, screw withdrawal and fatigue | connector_type, panel_type, edge_distance_mm |
| `kitchen_wall_anchoring` | Cabinet hangers, rails, fixing layouts, substrate and anchor requirements | substrate, anchor_model, hanger_model, fixing_count |
| `kitchen_ergonomics_accessibility` | Reach zones, working height, accessible design, circulation and appliance layout | user_needs, accessibility_scope, clearance_mm |
| `kitchen_moisture_protection` | Sink/dishwasher areas, edge sealing, swelling risks, water resistance and ventilation | exposure_zone, edge_treatment, board_grade |
| `kitchen_appliance_integration` | Manufacturer-specific fit/ventilation/heat clearances and installation constraints | appliance_brand, model, appliance_type |
| `kitchen_structural_validation` | Validated methods/tests for drawer load, shelf deflection, connections, wall-unit loads, tipping, worktops | calculation_id, test_method, version |

If equivalent collections already exist, **extend/map to them instead of duplicating content**. Add the kitchen namespace to the existing search router and preserve backwards compatibility.

## 2. Source registry additions (Germany/EU first)

A URL is an official reference, **not automatic permission to crawl/embed**. Store link-only metadata for copyrighted standards and manufacturer documents until explicit ingestion rights are recorded.

| Source | Intended use | Ingestion default |
|---|---|---|
| [DIN EN 14749:2022-07](https://www.dinmedia.de/de/norm/din-en-14749/347372014) — domestic/kitchen storage units and worktops | Primary furniture safety and tests | `metadata_only` (licensed standard) |
| [DIN EN 15939:2019-11](https://www.dinmedia.de/de/norm/din-en-15939/287424150) — cabinet hanging devices | Test methods for wall-hanging hardware **not the wall itself** | `metadata_only` |
| [DIN Media catalogue](https://www.dinmedia.de/) — find/check **DIN EN 16122** | Storage furniture strength/durability/stability test methods; verify edition and relevance | `metadata_only` |
| [DIN Media catalogue](https://www.dinmedia.de/) — find/check **DIN EN 312** and **DIN EN 622-5** | Particleboard and MDF grades/specifications; verify edition | `metadata_only` |
| [DIN Media catalogue](https://www.dinmedia.de/) — find/check **DIN 18040-2** | Accessibility **when applicable**; not a universal kitchen-size mandate | `metadata_only` |
| [EU General Product Safety Regulation 2023/988](https://eur-lex.europa.eu/eli/reg/2023/988/oj/eng) | Consumer-product safety obligations where applicable | Official legal text; check reuse terms |
| [Berlin building regulations](https://gesetze.berlin.de/) | Building/installation impacts where actually applicable; check current BauO Bln | Official link; check reuse terms |
| [USDA Wood Handbook](https://research.fs.usda.gov/fpl/wood-handbook) | Public-domain-candidate engineering methods: wood, composites, fastenings, deflection | Review specific chapter and third-party rights |
| [EGGER technical documentation](https://www.egger.com/) | Grade/thickness-specific panels, bending modulus, moisture properties | `metadata_only` until permitted |
| [Blum technical catalogue](https://publications.blum.com/) | Exact drawer runner, hinge and lift-system model specs | `metadata_only` until permitted |
| [Hettich](https://www.hettich.com/) and [Häfele](https://www.hafele.de/) product documentation | Alternative drawer/hardware/fastener model specs | `metadata_only` until permitted |
| Exact appliance and worktop manufacturer's installation manual | Model-specific cutouts, ventilation, heat spacing, support limits | `metadata_only` until permitted |

Use standards as **applicability and test-method references**, not proof that a design complies. Check publisher status/edition when updating the registry.

## 3. Add records to existing schemas (nonbreaking migration)

Minimum additional fields, nullable for legacy documents:

```yaml
collection: kitchen_drawer_systems
source_id: blum_runner_exact_model_revision
source_url: https://publications.blum.com/
source_kind: manufacturer_datasheet
license_status: permission_pending
approved_for_embedding: false
jurisdiction: DE
standard_id: null
edition_or_revision: null
retrieved_at: null
page_or_section: null
product:
  manufacturer: Blum
  model: null             # exact product identifier required
  part_number: null
  variant: null
constraints:
  nominal_load_kg: null   # keep null until verified from exact manual
  runner_length_mm: null
  drawer_width_mm: null
  drawer_depth_mm: null
  panel_thickness_mm: null
  mounting_conditions: null
verification_status: unverified
```

Separate structured **numerical/product tables** from semantic chunks; key by manufacturer + exact SKU/model + revision + material grade/thickness. Store units, limits, conditions, document/page provenance and retrieval date. Do **not** populate engineering values with generic assumptions or LLM-generated numbers.

## 4. Retrieval and engineering rules

1. Route kitchen design requests to relevant kitchen namespaces **and** existing `material_datasheets`, `hardware_manuals`, `furniture_standards_index`, `eu_de_berlin_law`, `product_safety` and structural calculation resources. Apply jurisdiction `DE` / `EU` filters where relevant.
2. Evidence priority: applicable law → licensed applicable standard → exact product manufacturer manual/data → validated engineering calculation → general woodworking guidance. Never treat guidance as certification.
3. **Cabinets:** verify panel grade/thickness, span/support conditions, back-panel contribution (only if justified), joint load path, moisture environment, and tipping/stability. No default claim that 18 mm is adequate.
4. **Drawers:** require exact runner series/variant and mounting geometry; check declared load capacity and conditions, loaded drawer bottom, box joints, fasteners, and extension-induced moments. A runner rating does not certify the entire drawer or cabinet.
5. **Wall cabinets:** check contents + cabinet self-weight, lever arms, hanger/rail capacity, wall substrate, verified anchors, installation details and substrate condition. DIN EN 15939 does **not** verify the wall fixings/substrate.
6. **Doors/hinges:** account for door mass/dimensions, hinge type/count, fixing substrate and manufacturer's mounting instructions; don't infer hinge count from door height alone.
7. **Moisture/appliances:** differentiate P2 versus boards rated for humid conditions, check cut edges and sealing, sink leaks, steam, dishwasher/oven heat, and appliance-maker clearances. Never invent ventilation distances.
8. **Countertops:** use material + thickness + manufacturer-specific overhang/cutout/support limits, including concentrated loads. No universal overhang rule.
9. For calculations, reuse the existing deterministic tools. Return `NOT_VERIFIED` where load, material grade, attachment, geometry, or a verified rating is missing; do not manufacture ratings, factors or DIN compliance statements.
10. Outputs must show **assumptions, dimensions, load cases, calculation outcome, reference URL + page/section, missing inputs, safety concerns, and whether this is preliminary guidance or validated against a named test**.

## 5. Codex implementation tasks

- [ ] Inspect existing collections, registry, router, embeddings model, APIs, licensing gate, calculators, tests and migrations; document mappings in the PR.
- [ ] Add/map the 10 logical kitchen namespaces without changing or deleting existing vectors.
- [ ] Extend registry taxonomies, metadata schemas, citation format and search filters; write backward-compatible migration and rollback.
- [ ] Seed **link-only** records for restricted sources above; ingest full content only with documented `approved_for_embedding=true` and confirmed scope of rights.
- [ ] Extract numeric product attributes only from permitted, versioned primary evidence; keep unknown values `null`.
- [ ] Add query-intent routing for: base/wall cabinet, sink unit, drawer, hinge, hanger/anchor, moisture, appliance, ergonomics, worktop.
- [ ] Connect/reuse deterministic checks for shelf/box deflection, joint capacity, drawer runner limits, hanger/anchor loads and tipping; mark unsupported checks `NOT_VERIFIED`.
- [ ] Add regression tests ensuring previous furniture queries still work; add kitchen-specific tests below.
- [ ] Produce a migration report: created/mapped namespaces, indexed vs link-only sources, tests passed, unresolved licensing or numerical evidence.

## 6. Acceptance tests / negative cases

| Query | Expected behavior |
|---|---|
| "Can I use 18 mm P2 for a 900 mm kitchen shelf?" | Ask for load/depth/supports; calculate only with verified E/strength and creep criteria; otherwise `NOT_VERIFIED` |
| "Can a 40 kg rated runner hold a 40 kg kitchen drawer?" | Check exact model, rating conditions, drawer self-weight, fixing/box and cabinet support; **no automatic yes** |
| "How many anchors for a 1200 mm wall cabinet on plasterboard?" | Require wall/system structure and verified fixing specification; no invented anchor count |
| "Use Blum data for a Hettich runner" | Reject cross-manufacturer substitution; retrieve exact part |
| "Is DIN EN 14749 compliance confirmed?" | Never assert compliance without documented applicable tests/evidence |
| "What gap does my integrated oven need?" | Require exact appliance model/manual before stating a clearance |
| "Can I use this copyrighted DIN PDF because it is online?" | License gate blocks full-text ingestion without permission |

## Definition of done

Existing RAG still works; kitchen queries route correctly; new source records are traceable and license-gated; calculations use verified inputs and deterministic tools; safety-critical unknowns produce `NOT_VERIFIED`; tests pass. **Do not build a new RAG service.**

**Codex invocation:** "Read `kitchen_cabinet_drawer_rag_extension.md`, inspect the existing RAG implementation, and implement this as a backward-compatible extension. Reuse current services, enforce license gates and safety checks, and report migrations, tests, and unresolved evidence."
