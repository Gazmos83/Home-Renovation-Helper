## Why

The RAG foundation can retrieve authorised engineering evidence but cannot calculate a verified shelf, joint, fixing or tipping result. Add deterministic, bounded calculations that consume reviewed numerical records and version-specific geometry, so neither vector search nor an LLM invents safety ratings.

## What Changes

- Depend on the [RAG foundation](../archive/2026-10-15-furniture-engineering-rag-foundation/proposal.md). Keep this a later, separately applicable change; the foundation remains useful without calculators. Production use does not depend on promoting the quarantine experiment.
- Add a closed calculator registry for bending/deflection, long-term creep, joint resistance, exact hardware capacity, anchorage and tipping. Each implemented method declares supported geometry/load cases, mandatory inputs, units, cited method revision and reviewed reference cases.
- Use SI units and explicit mass-to-force conversion (`F_N = mass_kg × 9.81`). Distinguish mean/test strength from allowable design resistance, and retain ranges, duration, moisture, orientation and load conditions. No guessed safety factors or acceptance limits.
- Support ordinary rectangular shelf cases first; compound folded geometry, unknown joint/load paths and out-of-domain cases return `NOT VERIFIED` rather than being simplified silently. Family-by-family review gates define when each method can be enabled.
- Give Designer and Researcher a calculation tool and structured report. Dimensions come from the exact stored spec version; material/product bindings, loads, supports and installation facts are explicit confirmed assessment inputs.
- Keep immutable calculation reports with input hashes, source/property revisions, method version, assumptions, results, limits and unresolved checks. A passing check is scoped to its method and inputs and never means whole-piece conformity.
- Keep mandatory gates for wall substrate/anchors, TV and child-climbing loads, countertop product instructions, and model-specific Murphy-bed manuals and qualified review. Murphy-bed mechanism/kinematic certification and arbitrary structural simulation are outside this proposal.
- A design remains creatable/renderable as preliminary geometry when assessment is incomplete. Existing piece approval and final-render approval cannot approve engineering safety.

**Ladder step:** supports step 1 with a separate assessment contract; no generator or live Blender change. **Agents:** Designer and Researcher (calculate/report), Foreman (engineering intent); Reviewer remains a visual reviewer. **Render guard and bpy allow-list:** unaffected; calculators run without Blender.

## Capabilities

### New Capabilities

- `engineering-calculations`: method registry, deterministic numerical checks, applicability limits, reviewed inputs and reproducible reports.

### Modified Capabilities

- `design-agents`: expose calculation tools to existing specialists and relay code-generated results without model arithmetic or safety approval.
- `house-file`: retain immutable engineering assessments scoped to piece/version and conversation, with explicit stale-report handling.

## Impact

- New backend engineering calculation modules, Pydantic assessment schemas, report persistence/migration, developer method status and owner report routes; plugin manifest/tool headers and house-file context summaries. Reuse current spec-derived shelf geometry and source/property IDs; do not extend drilling calculators into structural calculators.
- **Conflicts:** material slots currently identify a display/material name and thickness rather than a verified grade/product; the shelf-span rule checks width but not loads or creep; bracket-count guidance is not an anchor resistance; visual approval currently drives pricing/composition; summaries can truncate provenance. Separate bindings and assessment status resolve these without changing cut lists or visual approval semantics.
- Folded carcasses and partial dividers already exist. Board cut width, widest-bay warnings and a divider's fixed-shelf attachment do not establish structural support or joint resistance. The first methods must reject unsupported load paths explicitly.
- Qualified review of each method, reference values and applicable design criteria is a release dependency. The system does not assert that every freestanding item falls under Berlin building rules or that a DIN edition applies merely because it is indexed.
- Estimate: **20–40 additional developer days** (160–320 hours), low-to-medium confidence, for bounded methods and integration, not a general engineering solver. Qualified engineering review and obtaining usable exact product/anchor documents are external dependencies. Breakdown and limits are in `design.md`.
- No calculator implementation, numerical safety rating, database migration or render is performed by this proposal.
