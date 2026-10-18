---
name: blender-design-package
description: Create or refine Blender furniture, cabinetry, light fixtures and single-room packages with realistic renders, dimensioned components and traceable cut lists. Use for modeling, detailing, lighting, stills and optional frame-scrub viewers.
---

# Blender Design Package

Optimize model context and repeated work while preserving dimensional accuracy and presentation quality. A convincing image alone does not establish fabrication readiness.

## Project contract

Read [CLAUDE.md](../../../CLAUDE.md) and [Project_reference.md](../../../Project_reference.md) once per task, reusing context already loaded. They own implementation and product scope. Blender integration is planned for Tier 2; reference assets do not establish shipped features.

App jobs use maintained, backend-run parametric generators with validated specifications; the runtime agent supplies parameters, never executable bpy. Blender MCP and this skill support operator authoring. Default app scope is furniture in one rectangular room with openings; complex spaces use the operator workflow.

## Load detail when needed

- Read [fabrication.md](references/fabrication.md) for structural changes, component specifications, cut lists or fabrication-readiness claims.
- Read [rendering.md](references/rendering.md) for materials, fixtures, lighting, final images or frame sequences.
- Render-only adjustments preserve the existing specification and part identities. A requested blockout can omit finish detail and remains a draft.

## Workflow

1. Inspect existing specifications, relevant objects and available generators. Confirm requested deliverables, audience, dimensions and unresolved construction choices. Ask about missing information that affects fit, cutting or the requested result; use clearly recorded assumptions only for drafts.
2. Verify the actual Blender version and available tools once. Prefer headless execution for repeatable generators; use MCP when editing an operator scene. Do not require MCP, Poly Haven or IES for every job. Preserve an existing scene before substantial edits.
3. Keep authoritative dimensions in millimetres and convert explicitly to metres for Blender geometry. Derive component geometry, cut lists and drawings from the same specification. Preserve manufacturing dimensions separately from presentation effects.
4. Reuse deterministic geometry/material helpers and cached assets. Make scoped parameter changes; batch related work into repeatable stages and return concise validation summaries. Avoid model calls per object or frame, repeated full scene dumps and unnecessary screenshots.
5. Check dimensions and assembly first, then inspect a small render for framing, grain, lighting and finish. Fix the observed issue before a final batch. Use EEVEE for the app pipeline; Cycles is available for operator finals when its quality benefit justifies the render cost. Keep token use and render time separate.
6. Deliver only the requested artifacts and state validation results and unresolved assumptions. Full app packages follow roadmap §7: model.blend, model.glb, spec.json with layers, cutlist.csv, hardware.csv and render.png. Frames/viewer are optional. Shop drawings derive from the same spec through the frontend SVG workflow.

Construction data, dimensions, hardware, costs and editable/scale-accurate models remain business-only. Client delivery uses presentation PNGs, including PNG frame viewers; omit measurement overlays and business metadata. Follow the app's role and filename allowlists when integrating artifacts.
