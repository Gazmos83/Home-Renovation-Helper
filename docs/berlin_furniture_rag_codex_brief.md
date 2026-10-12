# Furniture Engineering RAG — Berlin / Germany (Codex Brief)

**Scope:** Residential cabinets, shelving, entertainment units, kitchen counters and Murphy beds designed/installed in Berlin, Germany. **Reference date:** 2026-10-10. This is a source-selection and implementation brief, not a certification or engineering approval.

## Operating rules

- Use **SI/European metric units**: mm, m, kg, N, kN, N/mm² (MPa), kg/m³. Convert mass to force using `F_N = mass_kg × 9.81`; never treat kg as a unit of force.
- Prioritize **Germany/EU product safety requirements**, applicable DIN EN furniture standards, exact manufacturer instructions, and verified material datasheets. Recheck current editions and legal applicability per project.
- **DIN standards are generally copyrighted and are not automatically laws.** Store metadata and official links only until a license explicitly permits text extraction, embeddings, retrieval and commercial use.
- Furniture anchoring into a building requires verification of wall substrate, approved/appropriate anchors, installation geometry and load transfer. **DIN EN 15939 tests cabinet hanging devices, not the wall fixing itself.**
- Check applicability of Berlin building rules separately where an installation changes/affects the building. Do not assume every freestanding piece of furniture is governed by BauO Bln.

## Recommended source catalogue

| Priority | Authoritative source | Use in agent | Ingestion policy |
|---|---|---|---|
| P0 | [USDA Wood Handbook, FPL-GTR-282 (2021)](https://research.fs.usda.gov/treesearch/62200) ([PDF](https://research.fs.usda.gov/download/treesearch/62200.pdf)) | Wood/wood-composite properties, moisture, fasteners, bending and deflection | US government-authored material: public-domain candidate; inspect third-party content before import |
| P0 | [EU General Product Safety Regulation (EU) 2023/988](https://eur-lex.europa.eu/eli/reg/2023/988/oj/eng) | EU consumer-product safety obligations; applicable since 2024-12-13 | Official legal text; check official reuse terms |
| P0 | [Berlin Bauordnung (BauO Bln), current official text](https://gesetze.berlin.de/bsbe/?docId=jlr-NNLBE00004835NN00000000317&query=JURISLINK%3A%22BauO+BE+Inhaltsverzeichnis%22) | Determine whether building-related work and structural anchoring trigger local obligations | Link to official current version; check reuse terms; note §1 scope/exclusions |
| P1 | [DIN EN 14749:2022-07](https://www.dinmedia.de/de/norm/din-en-14749/347372014) | Safety/tests for domestic and kitchen storage units, kitchen worktops, TV furniture | **Licensed standard: do not embed without permission** |
| P1 | [DIN EN 15939:2019-11](https://www.dinmedia.de/de/norm/din-en-15939/287424150) | Strength/load tests for cabinet wall-hanging devices | **Licensed; wall anchor/substrate NOT covered** |
| P1 | [DIN information on EN 16122 test methods](https://www.din.de/de/ueber-normen-und-standards/nutzen-fuer-den-verbraucher/verbraucherrat/ueber-uns/veroeffentlichung-der-norm-din-en-14749-im-juli-2022-870388) | Storage-furniture strength, durability and stability testing context | Read free explanation; license standard text separately |
| P1 | [EGGER technical datasheets](https://www.egger.com/) | Actual P2/P3/etc. particleboard and MDF properties by exact product/thickness | Public to view; permission review before embedding |
| P1 | [Blum technical catalogue](https://publications.blum.com/2022/catalogue/en/) | Hinge/runner model-specific capacities, dimensions, mounting | Public to view; permission review before embedding |
| P1 | [Cosentino technical documentation](https://www.cosentino.com/en-ie/professional/cosentino-media-library/) | Product-specific countertop supports, cutouts and overhang limits | Public to view; permission review before embedding |
| P1 | Exact Murphy-bed mechanism manufacturer's installation manual (e.g. [Rockler](https://www.rockler.com/vertical-mount-murphy-bed-hardware-hardware)) | Pivot, mattress limits, fastening and assembly procedure | Only applicable to matching model/revision; permission review |

**Important:** Free PDF access does **not** equal authorization for indexing or commercial embedding. No permissively licensed European furniture standards are asserted here.

## Implementation specification for Codex

1. Create collections: `engineering_fundamentals`, `material_datasheets`, `hardware_manuals`, `furniture_standards_index`, `eu_de_berlin_law`, `product_safety`, `murphy_bed_safety`.
2. Implement an ingestion **license gate**: `approved_for_embedding = true` only with documented rights. Otherwise store **metadata + URL**; do not scrape full text.
3. Chunk approved PDFs by section, preserving table rows, equations, page references and version. Never detach an engineering value from units, grade, test condition, product ID or revision.
4. Required metadata: `publisher`, `title`, `source_url`, `standard_or_model`, `edition`, `retrieved_at`, `jurisdiction`, `applicable_furniture`, `material_grade`, `thickness_mm`, `license_status`, `page_section`, `verification_status`.
5. Maintain a **structured numerical database** alongside vector search for `E_MPa`, `bending_strength_MPa`, `density_kg_m3`, product capacity, thickness, allowable spans, conditions and provenance. Use null for unknown values.
6. Route numerical checks to deterministic, tested calculations: bending, deflection/long-term creep, joint resistance, hardware capacity, anchorage and tipping. Vector retrieval supplies evidence, **not** calculated safety approval.
7. Agent output must show: assumptions, loads, dimensions, exact product/grade, calculation result, source + page/section, warnings and missing inputs. Distinguish *preliminary design advice* from *tested/certified conformity*.

## Mandatory safety gates

- **Murphy beds:** Do not provide a final safe-to-build/anchor determination without a verified manufacturer-specific manual, full wall/anchor assessment and appropriate qualified review. Check crush, impact, unintended deployment and installation risks.
- **Wall-mounted cabinets and heavy shelves:** Confirm substrate (concrete, masonry, plasterboard/metal stud, etc.), fixing design and load distribution; never infer wall strength from cabinet hanger ratings.
- **Entertainment units:** Evaluate tipping and foreseeable misuse, including TV loads and child climbing.
- **Countertops:** Use material-specific instructions for unsupported overhangs, cutouts and supports; never extrapolate a quartz/ceramic limit to another stone or thickness.
- **All calculations:** If material grade, load, support geometry, duration or verified capacity is missing, ask for data or report `NOT VERIFIED`; never invent a load rating or compliance statement.

## Suggested first task to give Codex

> Implement the source registry, ingestion license gate, provenance-preserving PDF/HTML chunking and retrieval schema from this brief. Seed it with the USDA Wood Handbook only after reviewing its rights/third-party elements; seed DIN/EN, Berlin, EU and manufacturer sources as link-only records until approved. Add unit-aware material-property storage and a safety-gated answer template. Do not imply DIN conformity or calculate safe load capacities from unverified material values.
