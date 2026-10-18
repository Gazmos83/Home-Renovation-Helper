---
name: blender-apartment-render
description: "Reconstruct an apartment in Blender from photos and blueprints, then drive hyper-realistic Cycles renders through Blender MCP. Use when the user wants a photoreal 3D apartment, floor-plan to scene, camera-matched interior, or Blender MCP architectural visualization. Not for generic product shots, character rigs, or non-Blender DCC tools."
type: workflow
lifecycle: active
---

# Blender Apartment Render — Photoreal interior from plans and photos

Build a metric apartment shell from a blueprint and photos, push it into a live Blender session over MCP, and render Cycles stills that can be compared with the source photos.

## Use this skill when

- The user supplies or describes a floor plan plus room photos and wants a Blender scene or still.
- The user asks to connect Blender by MCP and model their apartment.
- The user wants a camera-matched, hyper-real interior render.

Do not use it for product-only shots, characters, or Maya/Unreal-only jobs.

## Knowledge graph

Start at `references/INDEX.md`.

- `references/measurement-intake.md` — manifest from plan and photos
- `references/mcp-connection.md` — discover tools and send code
- `references/shell-and-openings.md` — walls, doors, windows
- `references/photo-match.md` — cameras and compare loop
- `references/photoreal.md` — Cycles pass bar
- `references/materials.md` — BSDF starting points

## Workflow

1. **Intake.** Collect the blueprint, labeled photos, ceiling height, and which rooms to build. If files are missing, write the manifest skeleton and stop with the exact fields still needed. Do not invent room sizes.
2. **Manifest.** Copy `assets/apartment-manifest.example.json`. Fill metres, interior CCW polygons, openings, and one camera per photo. Read `references/measurement-intake.md`.
3. **Validate.** Run `python3 scripts/validate_manifest.py <manifest>`. Fix every error before Blender.
4. **Generate.** Run `python3 scripts/generate_shell.py <manifest> --out <chunk-dir>`. This writes `01_scene.py` through `05_render.py`.
5. **Connect.** Read `references/mcp-connection.md`. Discover Blender MCP tools. Confirm with Blender version print. Save a new `.blend` before edits.
6. **Build.** Execute chunks in order. Screenshot after rooms and after openings. Fix L-shaped floors and failed booleans using `references/shell-and-openings.md`.
7. **Match.** Place cameras from the manifest. Overlay each photo. Run the compare loop in `references/photo-match.md`. Dress only objects the photo or the user listed.
8. **Light and materials.** Apply `references/materials.md`. HDRI plus window portals from `references/photoreal.md`.
9. **Render.** 128-sample preview first. Final only after the pass bar. Report camera, samples, and PNG path.

## Rules

- Units are metres. Plan millimetres divided by 1000.
- One MCP code chunk at a time. Helpers must be repeated; only `bpy.data` persists.
- Trust dimensioned plans for size and photos for color, lens, and light.
- Do not call a still done if it fails the pass bar in `references/photoreal.md`.
- Poly Haven for generic furniture and HDRIs. Image-to-3D only for a distinctive hero prop.

## Common issues

| Problem | Action |
|---|---|
| No Blender tool in connected services | Tell the user to open Blender, enable the MCP addon, and connect the client. Do not fake a render. |
| `execute_blender_code` blocked by safe mode | Ask for safe mode off, or keep file writes on the agent side. |
| Chunk timeout | Split the room loop and resend. |
| GPU Cycles fails | Set `scene.cycles.device = 'CPU'` and continue the preview. |
| Photo and plan disagree | State the conflict. Keep plan dimensions. |
